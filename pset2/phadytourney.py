#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer
import operator

class PhadyTourney(Peer):
    def post_init(self):
        # print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"

        # // keep track of last available pieces of peers
        # // dict[peer.id] -> set(pieces)[numPieces]
        self.peerLastAvailable = dict()

        # // keep track of gained pieces per round
        # // dict[peer.id] -> list(set(pieces)[numPieces])[round]
        # // dict[peer.id] -> list(numPiecesDownloaded)[round]
        self.peerHistory = dict()
        self.peerHistoryNum = dict()

        # // keep track of downloads by peers
        # // dict[peer.id] -> list(list(download objects)[numberObjects])[round]
        # // dict[peer.id] -> list(numBlocks)[round]
        self.myDownloadsByPeer = dict()
        self.myDownloadBlocksByPeer = dict()

        # // keep track of download and upload rates
        # // dict[peer.id] -> float (estimated rate)
        self.peerDownloadRate = dict()
        self.peerUploadRate = dict()

        # // keep track of unchoked peers
        self.unchokedPeers = set()

        # // learning constants
        self.Gamma = 0.05
        self.Alpha = 0.1
        self.R = 5
        self.buffer = self.up_bw // 10
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.

        """ Commenting out debugging (DNY 2/9/2016)
        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))
        """

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in random.sample(isect, n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()

        # // bookkeeping for other peer's histories
        if round == 0: # // could switch to check size of .peerHistory dictionary instead
            # // initialize the peer info
            for peer in peers:
                self.peerHistory[peer.id] = [set()]
                self.peerHistoryNum[peer.id] = [0]
                self.peerLastAvailable[peer.id] = set(peer.available_pieces)
                self.myDownloadsByPeer[peer.id] = []
                self.myDownloadBlocksByPeer[peer.id] = []
                self.unchokedPeers.add(peer.id)
        else:
            # // do updates for peer info
            for peer in peers:
                av_set = set(peer.available_pieces)
                new_pieces = av_set.difference(
                            av_set.intersection(
                                self.peerLastAvailable[peer.id]))
                self.peerHistory[peer.id].append(new_pieces)
                self.peerHistoryNum[peer.id].append(len(new_pieces))

            # // update my download information
                # // initialize dictionary entries for this round
            for peer in peers:
                self.myDownloadsByPeer[peer.id].append([])
                self.myDownloadBlocksByPeer[peer.id].append(0)

                # // input info from downloads
            for download in history.downloads[history.last_round()]:
                assert(self.id == download.to_id)

                # // track the downloaded objects by each peer
                self.myDownloadsByPeer[download.from_id][round-1].append(download)

                # // track the number of blocks downloaded by each peer
                self.myDownloadBlocksByPeer[download.from_id][round-1]+=download.blocks

            # // estimate the download rates by filling self.peerDownloadRate
            for peer in peers:
                if self.myDownloadBlocksByPeer[peer.id][round-1] > 0:
                    # // if currently unchoked, note the rate
                    self.peerDownloadRate[peer.id] = self.myDownloadBlocksByPeer[peer.id][round-1]
                else:
                    # // otherwise, estimate split upload as the total download rate divided by the estimated slots
                    # // MAY NEED CASE WORK FOR ROUND 0
                    estimatedSlots = 4
                    avgDownload = sum(self.peerHistoryNum[peer.id])/float(len(self.peerHistoryNum[peer.id]))
                    self.peerDownloadRate[peer.id] = self.conf.blocks_per_piece * avgDownload / estimatedSlots

            # // estimate the upload rates by filling self.peerUploadRate
            if round <= 10:
                # // initialize the u_j for the first round
                self.peerUploadRate = self.peerDownloadRate
            else:
                for peer_id in self.unchokedPeers:
                    # // update the u_j
                    # // INCLUDE LOGIC FOR LAST R ROUNDS ???
                    i_r = min(round,self.R)
                    if all(self.myDownloadBlocksByPeer[peer_id][round-1-i] > 0 for i in range(i_r)):
                        # // if unchoked, decrease estimated upload
                        self.peerUploadRate[peer_id] = self.peerUploadRate[peer_id] * (1 - self.Gamma)
                    else:
                        # // else increase estimated u_j
                        self.peerUploadRate[peer_id] = self.peerUploadRate[peer_id] * (1 + self.Alpha)
        
            # // compute scores for peers
            scores = {}
            for peer in peers:
                if self.peerUploadRate[peer.id] == 0:
                    scores[peer.id] = 0.
                else:
                    scores[peer.id] = float(self.peerDownloadRate[peer.id])/self.peerUploadRate[peer.id]
            sortedScores = sorted(scores.iteritems(), key=operator.itemgetter(1), reverse=True)
            sortedIDs = [x[0] for x in sortedScores]

        """ Commented out debugging statements DNY 2/10/2016
        logging.debug("%s again.  It's round %d." % (
            self.id, round))

        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.
        """
        chosen = []
        bws = []
        if (len(requests) == 0 or round == 0):
            """ Commented out debugging statements DNY 2/10/2016
            logging.debug("No one wants my pieces!")
            """
            pass
        else:
            """ Commented out debugging statements DNY 2/10/2016
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"
            """

            bw_available = self.up_bw
            """"""
            print 
            print "start looking here"
            print "I am agent " + str(self.id)
            
            for ID in sortedIDs:
                """
                print "upload rate to " + str(ID)
                print self.peerUploadRate[ID]
                """
                bw_available -= (int(self.peerUploadRate[ID]) + self.buffer)
                if bw_available <= 0:
                    break
                chosen.append(ID)
                bws.append(int(self.peerUploadRate[ID]) + self.buffer)
            """
            print "here are my bws: " + str(bws)
            print "here is to whom: " + str(chosen)
            """
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        """ debugging prints 
        print
        print "Agent " + str(self.id) + " here!"
        print "I'm uploading " + str(len(uploads)) + " times"
        for upload in uploads:
            print "here's an upload:"
            print upload
        print 
        """
        return uploads
