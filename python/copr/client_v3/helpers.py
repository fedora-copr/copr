class List(list):
    def __init__(self, items, meta=None, response=None):
        list.__init__(self, items)
        self.meta = meta
        self.__response__ = response
