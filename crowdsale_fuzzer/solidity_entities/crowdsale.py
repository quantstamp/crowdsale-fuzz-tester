import random

import sys

from solidity_entities.environment import SolidityEnvironment
from solidity_entities.function import Function
from solidity_entities.token import Token
from test_writer import wrap_exception, gen_assert_equal, gen_big_int, gen_log, to_number, \
    wrap_token_balance_checks, wrap_sale_balance_checks, wrap_allowance_checks

ETHER = 10 ** 18
CROWDSALE_CAP = 100000 * ETHER
HUNDREDTH_UNIT = 10 ** 26
BILLION = 10 ** 9

def gen_user_str(user, wei=None):
    if not wei:
        return "{from: " + user + "}"
    else:
        return "{from: " + user + ", value: " + str(wei) + "}"



class CrowdsaleFuzzer:

    def __init__(self,
                 RNG,
                 solidity_environment,
                 token,
                 users,
                 owner,
                 beneficiary,
                 fundingGoalInEthers,
                 fundingCapInEthers,
                 minimumContributionInWei,
                 start,
                 durationInMinutes,
                 rateQspToEther):
        self.RNG = RNG
        self.env = solidity_environment
        self.token = token

        assert isinstance(self.RNG, random.Random)
        assert isinstance(self.env, SolidityEnvironment)
        assert isinstance(self.token, Token)

        self.all_users = users
        self.owner = owner
        self.beneficiary = beneficiary
        self.basic_users = [i for i in self.all_users if i not in [self.owner, self.beneficiary]]
        self.non_owner_users = [i for i in self.all_users if i != self.owner]
        self.fundingGoal = fundingGoalInEthers
        self.fundingCap = fundingCapInEthers
        self.minContribution = minimumContributionInWei
        self.startTime = start
        self.endTime = start + durationInMinutes * 60
        self.rate = rateQspToEther

        # other state variables
        self.saleClosed = False
        self.amountRaised = 0
        self.refundAmount = 0
        self.balanceOf = {}  # how much each donor has contributed to the crowdsale
        self.low_rate = 5000
        self.high_rate = 10000
        self.goal_reached = False
        self.cap_reached = False
        self.functions = self.gen_functions()


    def update_state_with_purchase(self, user, wei, mini_qsp):
        # update amount raised, the allowance of the crowdsale, and the balance of user in token and sale
        wei = int(wei)
        mini_qsp = int(mini_qsp)
        self.amountRaised += wei
        self.token.crowdsale_allowance -= mini_qsp
        self.token.balances[user] = self.token.balances.get(user, 0) + mini_qsp
        self.balanceOf[user] = self.balanceOf.get(user, 0) + wei

        # update goal and cap if exceeded
        if self.amountRaised > self.goal_reached:
            self.goal_reached = True
        if self.amountRaised > self.fundingCap:
            self.cap_reached = True
        print(wei / 10**18)


    # TODO: automatically infer failures
    def gen_functions(self):
        """
        Generate function signatures for testing vectors
        """
        # TODO payable, nonReentrant
        terminate = Function(self.terminate, ["onlyOwner"], None)
        setRate = Function(self.setRate, ["onlyOwner"], ["rateAbove", "rateBelow"])
        ownerAllocateTokens = Function(self.ownerAllocateTokens, ["onlyOwner", "validDestination"], ["exceedAllowance"])
        ownerUnlockFunds = Function(self.ownerUnlockFund, ["onlyOwner", "afterDeadline"], None)
        fallback = Function(self.fallback, ["whenNotPaused", "beforeDeadline", "saleNotClosed"])
        arr = [terminate, setRate, ownerAllocateTokens, ownerUnlockFunds, fallback]
        return arr

    def onlyOwner(self, function_name, error_message, parameters):
        # instantiate parameters locally
        if not parameters:
            parameters = {}

        user = parameters.get("user", self.RNG.choice(self.non_owner_users))
        # end parameter instantiation

        user_str = gen_user_str(user)
        s = "await " + function_name + "(" + user_str + ");"
        s = wrap_exception(s, error_message)
        return s

    def terminate(self, fail, parameters=None):
        # can only fail if run as a non-owner
        # instantiate parameters locally
        if not parameters:
            parameters = {}
        if fail:
            parameters["user"] = parameters.get("user", self.RNG.choice(self.non_owner_users))
        else:
            parameters["user"] = parameters.get("user", "owner")

        user = parameters["user"]
        # end parameter instantiation

        if not fail:
            # run as the owner
            user_str = gen_user_str(user)
            s = "await sale.terminate(" + user_str + ");\n"
            s += "let closed = await sale.saleClosed();\n"
            s += "assert(closed, 'sale should be closed after owner terminates it');"
            self.saleClosed = True
        else:
            s = self.onlyOwner("sale.terminate", "only the owner can terminate the crowd sale", parameters)
        return s;

    def ownerUnlockFund(self, fail, parameters=None):
        # can only fail if run as a non-owner, or before deadline
        # instantiate parameters locally
        if not parameters:
            parameters = {}
        if fail == "onlyOwner":
            parameters["user"] = parameters.get("user", self.RNG.choice(self.non_owner_users))
        else:
            parameters["user"] = parameters.get("user", "owner")
        if fail == "afterDeadline":
            sys.exit("TODO afterDeadline")
        elif not fail:
            parameters["user"] = parameters.get("user", "owner")
        else:
            sys.exit("Missing case in ownerUnlockFund")

        user = parameters["user"]
        # end parameter instantiation

        if not fail:
            # run as the owner
            user_str = gen_user_str(user)
            s = "await sale.ownerUnlockFund(" + user_str + ");\n"
            s += "var goal_reached = await sale.fundingGoalReached();\n"
            s += "assert(goal_reached, 'fundingGoalReached should be false after calling, allowing users to withdraw');"
            self.saleClosed = True
        elif fail == "onlyOwner":
            s = self.onlyOwner("sale.ownerUnlockFund",
                                    "only the owner can unlock funds from the crowd sale",
                               parameters)
        elif fail == "afterDeadline":
            # TODO
            sys.exit("TODO afterDeadline")
        return s;


    def setRate(self, fail, parameters=None):
        # instantiate parameters locally
        if not parameters:
            parameters = {}
        if fail == "onlyOwner":
            parameters["user"] = parameters.get("user", self.RNG.choice(self.non_owner_users))
        else:
            parameters["user"] = parameters.get("user", "owner")
        if fail == "rateAbove":
            parameters["rate"] = parameters.get("rate", self.RNG.randint(self.high_rate + 1, BILLION))
        elif fail == "rateBelow":
            parameters["rate"] = parameters.get("rate", self.RNG.randint(0, self.low_rate - 1))
        else:
            self.RNG.randint(self.low_rate, self.high_rate)

        user = parameters["user"]
        rate = parameters["rate"]
        user_str = gen_user_str(user)
        # end parameter instantiation

        if not fail:
            # run as the owner
            s = "await sale.setRate(" + str(rate) + ", " + user_str + ");\n"
            s += "var currentRate = await sale.rate();\n"
            s += gen_assert_equal("currentRate", rate, "the rate should be set to the new value")
            self.rate = rate
        elif fail == "onlyOwner":
            s = self.onlyOwner("sale.setRate", "only the owner can set the rate")
        elif fail == "rateAbove" or fail == "rateBelow":
            s = "await sale.setRate(" + str(rate) + ", " + user_str + ");\n"
            s = wrap_exception(s, "the new rate must be within the bounds")
        if fail:
            s += "var currentRate = await sale.rate();\n"
            s += gen_assert_equal("currentRate", self.rate, "the rate should not have changed")
        return s;

    def ownerAllocateTokens(self, fail, parameters=None):
        # TODO: refactor
        # TODO: fresh var generator
        # instantiate parameters locally
        if not parameters:
            parameters = {}
        if fail == "onlyOwner":
            parameters["user"] = parameters.get("user", self.RNG.choice(self.non_owner_users))
        else:
            parameters["user"] = parameters.get("user", "owner")
        if fail == "validDestination":
            bad_users = ["sale.address", "0x0", "token.owner()"]
            parameters["to_user"] = parameters.get("to_user", self.RNG.choice(bad_users))
        else:
            parameters["to_user"] = parameters.get("to_user", self.RNG.choice(self.all_users))
        if fail == "exceedAllowance":
            parameters["amount_mini_qsp"] = parameters.get("amount_mini_qsp",
                                                           self.RNG.randint(self.token.crowdsale_allowance + 1,
                                                                            self.token.crowdsale_allowance + BILLION))
        else:
            parameters["amount_mini_qsp"] = parameters.get("amount_mini_qsp",
                                                           self.RNG.randint(0, self.token.crowdsale_allowance))
        parameters["amount_wei"] = parameters.get("amount_wei", self.RNG.randint(0, CROWDSALE_CAP))

        user = parameters["user"]
        user_str = gen_user_str(user)
        to_user = parameters["to_user"]
        amount_mini_qsp = parameters["amount_mini_qsp"]
        amount_wei = parameters["amount_wei"]
        # end parameter instantiation

        if not fail:
            s = "await sale.ownerAllocateTokens(" + \
                ", ".join([to_user, amount_wei, amount_mini_qsp, user_str]) + ");\n"

            # assert that token.balances[to_user] increases by amount_mini_qsp
            vid = "token_balance_" + to_user
            s = wrap_token_balance_checks(s, to_user, vid)
            l = vid + "_before.add(" + gen_big_int(amount_mini_qsp) + ")"
            r = vid + "_after"
            s += gen_assert_equal(to_number(l), to_number(r),
                                  "the token balance of the to_user should increase after ownerAllocateTokens")

            # assert that the sale.balanceOf[to_user] increases by amount_wei
            vid = "sale_balance_" + to_user
            s = wrap_sale_balance_checks(s, to_user, vid)
            l = vid + "_before.add(" + gen_big_int(amount_wei) + ")"
            r = vid + "_after"
            s += gen_assert_equal(to_number(l), to_number(r),
                                  "the sale balance of the to_user should increase after ownerAllocateTokens")

            # assert that the allowance of crowdsale decreases by amount_mini_qsp
            vid = "crowdsale_allowance"
            s = wrap_allowance_checks(s, "sale.address", vid)
            l = vid + "_before.minus(" + gen_big_int(amount_mini_qsp) + ")"
            r = vid + "_after"
            s += gen_assert_equal(to_number(l), to_number(r),
                                  "the allowance of the crowdsale should decrease by amount_mini_qsp")

            # update the state of crowdsale.py
            self.update_state_with_purchase(to_user, amount_wei, amount_mini_qsp)

            # assert that the goalReached field has changed if necessary
            s += "var goal_reached = await sale.fundingGoalReached();\n"
            if self.goal_reached:
                s += "assert(goal_reached, 'the funding goal has been reached and should be true');\n"
            else:
                s += "assert(!goal_reached, 'the funding goal has not been reached and should be false');\n"

            # assert that the capReached field has changed if necessary
            s += "var cap_reached = await sale.fundingCapReached();\n"
            if self.cap_reached:
                s += "assert(cap_reached, 'the funding cap has been reached and should be true');\n"
            else:
                s += "assert(!cap_reached, 'the funding cap has not been reached and should be false');\n"
        elif fail == "onlyOwner":
            s = self.onlyOwner("sale.ownerAllocateTokens",
                                    "only the owner can call ownerAllocateTokens",
                               parameters)
        elif fail == "validDestination":
            s = "await sale.ownerAllocateTokens(" + \
                ", ".join([to_user, amount_wei, amount_mini_qsp, user_str]) + ");\n"
            s = wrap_exception(s, "the to-address is not valid for allocating tokens")
        elif fail == "exceedAllowance":
            s = "await sale.ownerAllocateTokens(" + \
                ", ".join([to_user, amount_wei, amount_mini_qsp, user_str]) + ");\n"
            s = wrap_exception(s, "the amount of mini-QSP exceeds the crowdsale's allowance")
        if fail:
            s += "var currentCrowdSaleAllowance = await token.crowdSaleAllowance();\n"
            s += gen_assert_equal("currentCrowdSaleAllowance",
                                  self.token.crowdsale_allowance,
                                  "the crowdsale allowance should not have changed")
        return s;

    def fallback(self, fail, parameters=None):
        # TODO: cases
        # case where the contribution is less than the minimum
        # case where the crowdsale is closed
        # case where the crowdsale is after the deadline
        # case where the crowdsale is paused
        # case where the amount exceeds cap
        # case where the amount exceeds goal but not cap

        # instantiate parameters locally
        # PARAMETERS: user, wei
        # fail: belowMinContribution
        if not parameters:
            parameters = {}
        parameters["user"] = parameters.get("user", self.RNG.choice(self.all_users))
        if fail == "belowMinContribution":
            parameters["wei"] = parameters.get("wei", self.RNG.randint(0, int(0.1*ETHER - 1)))
        else:
            parameters["wei"] = parameters.get("wei", self.RNG.randint(int(0.1 * ETHER), ETHER))

        user = parameters["user"]
        wei = parameters["wei"]
        user_str = gen_user_str(user, wei)
        # end parameter instantiation


        if not fail:
            s = "await sale.sendTransaction(" + user_str + ");\n"
            # assert that the balance of the user in token is increased (qsp = wei * rate)
            # assert that the balance of the user in sale is increased (wei)
            # assert that the amountRaised field has increased
            # assert that the goalReached field has changed if necessary
            # assert that the capReached field has changed if necessary
            print("TODO payable")

        else:
            print("TODO finish payable")
            s = ""
        return s;