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



    def gen_functions(self):
        """
        Generate function signatures for testing vectors
        """
        # TODO payable, nonReentrant
        terminate = Function(self.fuzz_terminate, ["onlyOwner"], None)
        setRate = Function(self.fuzz_setRate, ["onlyOwner"], ["rateAbove", "rateBelow"])
        ownerAllocateTokens = Function(self.fuzz_ownerAllocateTokens, ["onlyOwner", "validDestination"] , ["exceedAllowance"])
        ownerUnlockFunds = Function(self.fuzz_ownerUnlockFund, ["onlyOwner", "afterDeadline"], None)
        fallback = Function(self.fuzz_fallback, ["whenNotPaused", "beforeDeadline", "saleNotClosed"])
        arr = [terminate, setRate, ownerAllocateTokens, ownerUnlockFunds, fallback]
        return arr

    def fuzz_onlyOwner(self, function_name, error_message):
        user = self.RNG.choice(self.non_owner_users)
        user_str = gen_user_str(user)
        s = "await " + function_name + "(" + user_str + ");"
        s = wrap_exception(s, error_message)
        return s

    def fuzz_terminate(self, fail):
        # can only fail if run as a non-owner
        if not fail:
            # run as the owner
            user_str = gen_user_str("owner")
            s = "await sale.terminate(" + user_str + ");\n"
            s += "let closed = await sale.saleClosed();\n"
            s += "assert(closed, 'sale should be closed after owner terminates it');"
            self.saleClosed = True
        else:
            s = self.fuzz_onlyOwner("sale.terminate", "only the owner can terminate the crowd sale")
        return s;

    def fuzz_ownerUnlockFund(self, fail):
        # can only fail if run as a non-owner, or before deadline
        if not fail:
            # run as the owner
            user_str = gen_user_str("owner")
            s = "await sale.ownerUnlockFund(" + user_str + ");\n"
            s += "var goal_reached = await sale.fundingGoalReached();\n"
            s += "assert(goal_reached, 'fundingGoalReached should be false after calling, allowing users to withdraw');"
            self.saleClosed = True
        elif fail == "onlyOwner":
            s = self.fuzz_onlyOwner("sale.ownerUnlockFund", "only the owner can unlock funds from the crowd sale")
        elif fail == "afterDeadline":
            # TODO
            sys.exit("TODO afterDeadline")
        return s;


    def fuzz_setRate(self, fail):
        if not fail:
            # run as the owner
            user_str = gen_user_str("owner")
            rate = self.RNG.randint(self.low_rate, self.high_rate)
            s = "await sale.setRate(" + str(rate) + ", " + user_str + ");\n"
            s += "var currentRate = await sale.rate();\n"
            s += gen_assert_equal("currentRate", rate, "the rate should be set to the new value")

            self.rate = rate
        elif fail == "onlyOwner":
            s = self.fuzz_onlyOwner("sale.setRate", "only the owner can set the rate")
        elif fail == "rateAbove" or fail == "rateBelow":

            if fail == "rateAbove":
                rate = self.RNG.randint(self.high_rate + 1, BILLION)
            else:
                rate = self.RNG.randint(0, self.low_rate - 1)
            user_str = gen_user_str("owner")
            s = "await sale.setRate(" + str(rate) + ", " + user_str + ");\n"
            s = wrap_exception(s, "the new rate must be within the bounds")
        if fail:
            s += "var currentRate = await sale.rate();\n"
            s += gen_assert_equal("currentRate", self.rate, "the rate should not have changed")

        return s;

    def fuzz_ownerAllocateTokens(self, fail):
        # TODO: refactor
        # TODO: fresh var generator
        if not fail:
            # run as the owner
            user_str = gen_user_str("owner")
            to_user = self.RNG.choice(self.all_users)
            amount_mini_qsp = str(self.RNG.randint(0, self.token.crowdsale_allowance))
            amount_wei = str(self.RNG.randint(0, CROWDSALE_CAP))
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
            s = self.fuzz_onlyOwner("sale.ownerAllocateTokens", "only the owner can call ownerAllocateTokens")
        elif fail == "validDestination":
            bad_users = ["sale.address", "0x0", "token.owner()"]  # TODO: abstract this
            user_str = gen_user_str("owner")
            to_user = self.RNG.choice(bad_users)
            amount_mini_qsp = str(self.RNG.randint(0, self.token.crowdsale_allowance))
            amount_wei = str(self.RNG.randint(0, CROWDSALE_CAP))
            s = "await sale.ownerAllocateTokens(" + \
                ", ".join([to_user, amount_wei, amount_mini_qsp, user_str]) + ");\n"
            s = wrap_exception(s, "the to-address is not valid for allocating tokens")
        elif fail == "exceedAllowance":
            user_str = gen_user_str("owner")
            to_user = self.RNG.choice(self.all_users)
            amount_wei = str(self.RNG.randint(0, CROWDSALE_CAP))
            amount_mini_qsp = str(self.RNG.randint(self.token.crowdsale_allowance + 1,
                                                   self.token.crowdsale_allowance + BILLION))
            s = "await sale.ownerAllocateTokens(" + \
                ", ".join([to_user, amount_wei, amount_mini_qsp, user_str]) + ");\n"
            s = wrap_exception(s, "the amount of mini-QSP exceeds the crowdsale's allowance")
        if fail:
            s += "var currentCrowdSaleAllowance = await token.crowdSaleAllowance();\n"
            s += gen_assert_equal("currentCrowdSaleAllowance",
                                  self.token.crowdsale_allowance,
                                  "the crowdsale allowance should not have changed")
        return s;

    def fuzz_fallback(self, fail):
        # TODO:
        # case where the contribution is less than the minimum
        # case where the crowdsale is closed
        # case where the crowdsale is after the deadline
        # case where the crowdsale is paused
        # case where the amount exceeds cap
        # case where the amount exceeds goal but not cap

        if not fail:
            user = self.RNG.choice(self.all_users)
            wei = self.RNG.randint(0, ETHER)  # TODO abstract
            user_str = gen_user_str(user, wei)
            #       await sale.sendTransaction({from: user2,  value: web3.toWei(amountEther, "ether")});
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