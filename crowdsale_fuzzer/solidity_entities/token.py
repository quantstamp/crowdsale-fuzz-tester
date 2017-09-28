class Token:

    def __init__(self,
                 initial_supply,
                 initial_crowdsale_allowance,
                 initial_admin_allowance):
        self.initial_supply = initial_supply
        self.initial_crowdsale_allowance = initial_crowdsale_allowance
        self.initial_admin_allowance = initial_admin_allowance
        self.supply = initial_supply
        self.crowdsale_allowance = initial_crowdsale_allowance  # TODO: incorporate into balances as well
        self.admin_allowance = initial_admin_allowance
        self.balances = {}  # the amount of tokens owned by each address
        self.allowances = {}  # the amount of tokens that a sender can transfer from a different user's balance
