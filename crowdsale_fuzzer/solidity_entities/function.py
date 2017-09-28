class Function:
    def __init__(self, function, modifiers=None, extra_failure_vectors = None):
        self.function = function
        self.modifiers = modifiers
        if extra_failure_vectors:
            self.extra_failure_vectors = extra_failure_vectors
        else:
            self.extra_failure_vectors = []

    def failure_types(self):
        return self.modifiers + self.extra_failure_vectors


    def __str__(self):
        s = self.function.__name__ + " " + " ".join(self.modifiers)
        return s

    def __repr__(self):
        return self.__str__()
