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

        # make set of pieces I need
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.
        requests = []   # We'll put all the things we want here
        random.shuffle(needed_pieces)   # break symmetry
        peers.sort(key=lambda p: p.id)   # just some sorting

        # dictionary of zero counts
        pieceCounts = dict(zip(range(len(self.pieces)), [0 for _ in range(len(self.pieces))]))

        # list of how common pieces are
        for peer in peers:
            for pieceNum in list(peer.available_pieces):
                pieceCounts[pieceNum] = pieceCounts[pieceNum] + 1

        # sort by rarest first
        pieceCountsSorted = sorted(pieceCounts, key=pieceCounts.get)

        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))

            # filter dictionary to keep only if in isect
            isectFiltered = [k for k in pieceCountsSorted if k in list(isect)]

            print "success!"
            # ask for first n pieces in isectFiltered
            m = min(len(isectFiltered),n)
            for piece_id in isectFiltered[0:m]:
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

        """ debugging statements 
        print 
        print "my requests:"
        print(requests)
        print
        print "my peers:"
        print(peers)
        print
        print "my history:"
        print(history)
        """

        if len(requests) == 0:
            chosen = []
            bws = []
        else:
            # // Score each requester
            requesters = []
            scores = {}

            for request in requests:
                # // 'requesters' is a list of requester_id's
                requesters.append(request.requester_id)
                requesters = list(set(requesters))

            numRequesters = len(requesters)

            if (numRequesters > 4 and round > 0):

                # // loop through requester and sum downloaded blocks from previous two rounds
                # dictionary of zero counts
                scores = dict(zip(requesters, [0]*numRequesters))

                if round > 1:
                    for i in [round-1,round-2]:
                        for dl in history.downloads[i]:
                            if dl.from_id in requesters:
                                scores[dl.from_id] += dl.blocks
                else:
                    for dl in history.downloads[round-1]:
                        if dl.from_id in requesters:
                            scores[dl.from_id] += dl.blocks

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
