import mastodon
import math

'''
Small class that is a downsampled object representation of pulses retrived on
ClioWire. Made for the sake of mudalirity, clarity, and for future additions.
'''
class Pulse:
    def __init__(self, id, content, reply_to_id=None):
        self.id=id
        self.reply_to_id=reply_to_id
        self.content=content

'''
Iterator that will retrieve pulses in a batch each time its next method is
called. Produce the illusion that all the pulses querried are in the RAM, while in
fact they are retrieved online each time the next is called.
'''
class PulseIterator():

    def __init__(self, api_instance, batch_size=200, hashtag=None, recent_id=None, oldest_id=None):
        self.batch_size = batch_size
        self.api_instance = api_instance
        self.hashtag = hashtag
        self.latest_id = recent_id
        self.curr = recent_id
        self.oldest_id = oldest_id
        self.hasnext = True

    def __iter__(self):
        return self


    def __next__(self):
        pulses = []
        retrieved = None
        if self.curr == None:
            retrieved = self.retrieve_pulses(None)
            self.curr = math.inf
            self.latest_id = 0
        else:
            retrieved = self.retrieve_pulses(self.curr)
        if retrieved == None or len(retrieved) == 0:
            raise StopIteration()
        else:
            for r in retrieved:
                nP = Pulse(r['id'], r['content'], r['in_reply_to_id'])
                if nP.id < self.curr:
                    self.curr = nP.id
                if nP.id > self.latest_id:
                    self.latest_id = nP.id
                pulses.append(nP)
        return pulses

    def __latest_id__(self):
        return self.latest_id


    def retrieve_pulses(self, recent_id):
        if self.hashtag == None:
            return self.api_instance.timeline_local(max_id=recent_id, since_id=self.oldest_id, limit=self.batch_size)
        else:
            return self.api_instance.timeline_hashtag(self.hashtag, max_id=recent_id, since_id=self.oldest_id, limit=self.batch_size, local=True)