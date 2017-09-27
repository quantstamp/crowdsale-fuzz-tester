

class SolidityEnvironment:

    def __init__(self):
        self.relative_eth_balances = {}  # stores the balance of each user/contract relative to before invoking the test
