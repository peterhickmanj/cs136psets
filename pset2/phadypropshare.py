# Implements Prop Share

import random
import logging

from messages import Upload, Request
from util import even_split, round_list
from peer import Peer

class PhadyPropShare(Peer):
    def post_init(self):
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
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

            # ask for first n pieces in isectFiltered
            m = min(len(isectFiltered),n)
            for piece_id in isectFiltered[0:m]:
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):

        print "test"

        # current round
        round = history.current_round()

        if len(requests) == 0 or round == 0:
            chosen = []
            bws = []

        else:

            # list of requesters
            requesters = []
            for request in requests:
                requesters.append(request.requester_id)
                requesters = list(set(requesters))

            # count downloads received from peer in last round
            peerIds = [x.id for x in peers]
            scores = dict(zip(peerIds, [0]*len(peerIds)))
            for dl in history.downloads[round-1]:
                if dl.from_id in requesters:
                    scores[dl.from_id] += dl.blocks

            # all downloads I got from requesters last round
            totalDownloads = sum(scores.values())

            # create dictionary of peers to upload to, and how much to send to them
            # Formula: u_j = 0.9*u_t*(d_j/d_t)
            numsToUpload = {}
            for requester in requesters:
                if totalDownloads != 0:
                    numsToUpload[requester] = 0.9 * self.up_bw * (scores[requester] / totalDownloads)
                else:
                    numsToUpload[requester] = 0

            # chosen and bandwidths for (possible) unchoking and rounding
            chosen = list(numsToUpload.keys())
            bwPreRound = list(numsToUpload.values())

            # choose someone to optimistically unchoke
            candidates = dict((k, v) for k, v in numsToUpload.items() if v == 0)

            # if there is a candidate, add to chosen and bws
            if len(candidates) != 0:
                winner = random.choice(candidates.keys())
                chosen.append(winner)
                bwPreRound.append(0.1 * self.up_bw)

            # otherwise, add 0.1*up_bw for all chosen
            else:
                bwPreRound = [x + (0.1 * self.up_bw) for x in bwPreRound]

            # round bandwidths using helper function (in util.py)
            bws = round_list(bwPreRound)

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
        print "####################################"
        print self.id
        print uploads
        print "######################################"
            
        return uploads
