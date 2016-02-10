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

class PhadyStd(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"

        # // optimistic unchoke ID
        self.optimisticID = 0
    
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

        """ Commenting out debugging prints (DNY 2/8/2016)
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

        # // look for rarest piece here
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
        # logging.debug("%s again.  It's round %d." % (
        #     self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        print 
        print "my requests:"
        print(requests)
        print
        print "my peers:"
        print(peers)
        print
        print "my history:"
        print(history)

        if len(requests) == 0:
            # logging.debug("No one wants my pieces!") 
            chosen = []
            bws = []
        else:
            # // Score each requester
            requesters = []
            scores = {}

            for request in requests:
                # // 'requesters' is a list of requester_id's
                requesters = list(set(requesters.append(request.requester_id)))

            numRequesters = len(requesters)

            if (numRequesters > 4 and round > 0):

                # // TRY TO CLEAN
                # // we did this wrong!!
                # // loop through requester and sum downloaded blocks from previous two rounds
                if round > 1:
                    for requester in requesters:
                        score = 0
                        dls = history.downloads[requester][round - 1]
                        for dl in dls:
                            score += dl.blocks
                        dls = history.downloads[requester][round - 2]
                        for dl in dls:
                            score += dl.blocks
                        scores[requester] = score
                else:
                    for requester in requesters:
                        score = 0
                        dls = history.downloads[requester][round - 1]
                        for dl in dls:
                            score += dl.blocks
                        scores[requester] = score

                # // get top three requesters
                sortedScores = sorted(scores.iteritems(), key=operator.itemgetter(1), reverse=True)
                chosen = [x[0] for x in sortedScores[:3]]

                # // if round % 3 == 0, optimistically unchoke someone (self.optimisticID)
                if (round % 3) == 0:
                    self.optimisticID = random.choice(sortedScores[3:])

                # // add uptimistic unchoked peer to chosen
                chosen.append(self.optimisticID)

                # // create upload objects, probably using even split
                bws = even_split(self.up_bw, len(chosen))
            else:
                chosen = requesters
                bws = even_split(self.up_bw, numRequesters)

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
