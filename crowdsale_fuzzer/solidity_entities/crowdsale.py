import random

import sys

from solidity_entities.environment import SolidityEnvironment
from solidity_entities.function import Function
from solidity_entities.token import Token
from test_writer import wrap_exception, gen_assert_equal, gen_big_int, gen_log, to_number, \
    wrap_token_balance_checks, wrap_sale_balance_checks, wrap_allowance_checks, balance_assertion_check, \
    goal_and_cap_assertion_checks, wrap_amount_raised, check_value, wrap_ether_balance_checks

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
                 token_admin,
                 fundingGoalInEthers,
                 fundingCapInEthers,
                 minimumContributionInWei,
                 start,
                 durationInMinutes,
                 rateQspToEther,
                 VERBOSE):
        self.RNG = RNG
        self.env = solidity_environment
        self.env.current_time = start
        self.token = token
        self.VERBOSE = VERBOSE

        assert isinstance(self.RNG, random.Random)
        assert isinstance(self.env, SolidityEnvironment)
        assert isinstance(self.token, Token)

        self.all_users = users
        self.owner = owner
        self.beneficiary = beneficiary
        self.token_admin = token_admin
        self.basic_users = [i for i in self.all_users if i not in [self.owner, self.beneficiary, self.token_admin]]
        self.non_owner_users = [i for i in self.all_users if i != self.owner]
        self.bad_destinations = ["sale.address", "0x0", "token.owner()", self.token_admin, "token.address"]

        self.fundingGoal = fundingGoalInEthers * ETHER
        self.fundingCap = fundingCapInEthers * ETHER
        self.minContribution = minimumContributionInWei
        self.startTime = start
        self.endTime = start + durationInMinutes * 60
        self.rate = rateQspToEther

        # other state variables
        self.saleClosed = False
        self.paused = False
        self.amountRaised = 0
        self.refundAmount = 0
        self.balanceOf = {}  # how much each donor has contributed to the crowdsale
        self.low_rate = 5000
        self.high_rate = 10000
        self.goal_reached = (self.amountRaised >= self.fundingGoal)
        self.cap_reached = (self.amountRaised >= self.fundingCap)
        self.functions = self.gen_functions()

    def update_state_for_new_contract(self, beneficiary, fundingGoalInEthers, fundingCapInEthers,
                                      minimumContributionInWei, start, durationInMinutes, rateQspToEther):
        self.beneficiary = beneficiary

        self.fundingGoal = fundingGoalInEthers * ETHER
        self.fundingCap = fundingCapInEthers * ETHER
        self.minContribution = minimumContributionInWei
        self.startTime = start
        self.endTime = start + durationInMinutes * 60
        self.rate = rateQspToEther

        # other state variables
        self.saleClosed = False
        self.paused = False
        self.amountRaised = 0
        self.refundAmount = 0
        self.balanceOf = {}  # how much each donor has contributed to the crowdsale
        self.goal_reached = (self.amountRaised >= self.fundingGoal)
        self.cap_reached = (self.amountRaised >= self.fundingCap)
        self.functions = self.gen_functions()


    def create_new_crowdsale(self, params, set_crowdsale=True):
        self.update_state_for_new_contract(*params)
        params = ", ".join([str(i) for i in params])
        s = "sale = await QuantstampSaleMock.new(" + params + ", token_address);\n"
        if set_crowdsale:
            s += "await token.setCrowdsale(sale.address, 0);\n"
        return s

    def update_state_with_purchase(self, user, wei, mini_qsp):
        # update amount raised, the allowance of the crowdsale, and the balance of user in token and sale
        # if mini_qsp is None, then mini_qsp = wei * rate
        wei = int(wei)
        if mini_qsp:
            mini_qsp = int(mini_qsp)
        else:
            mini_qsp = wei * self.rate
        self.amountRaised += wei
        self.token.crowdsale_allowance -= mini_qsp
        self.token.balances[user] = self.token.balances.get(user, 0) + mini_qsp
        self.balanceOf[user] = self.balanceOf.get(user, 0) + wei
        # update goal and cap if exceeded

        if self.amountRaised > self.fundingGoal:
            self.goal_reached = True
        if self.amountRaised > self.fundingCap:
            self.cap_reached = True

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

    def changeTime(self, time):
        s = "await sale.changeTime (" + str(time) + ", {from: owner});"
        self.env.current_time = time
        return s


    def checkTime(self):
        s = "var currTime = await sale._now();\n"
        s += gen_log("'Time: ' + currTime")
        return s

    def check_sale_state(self):
        s = gen_log("'================'")
        s += gen_log("'Crowdsale State:'")
        s += gen_log("")
        s += check_value("amountRaised", "sale.amountRaised()")
        s += check_value("refundAmount", "sale.refundAmount()")
        s += check_value("paused", "sale.paused()")
        s += check_value("saleClosed", "sale.saleClosed()")
        s += check_value("fundingGoalReached", "sale.fundingGoalReached()")
        s += check_value("fundingCapReached", "sale.fundingCapReached()")
        s += check_value("rate", "sale.rate()")
        s += check_value("startTime", "sale.startTime()")
        s += check_value("currentTime", "sale.currentTime()")
        s += check_value("endTime", "sale.endTime()")
        s += check_value("crowdsaleOngoing", "(startTime <= currentTime && currentTime <= endTime)")


        s += gen_log("'----------------'")


        return s

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

    # -------------------------------------------------------------------------------------------------------
    # Crowdsale Functions
    # -------------------------------------------------------------------------------------------------------

    def set_pause(self, fail=None, parameters=None):
        """
        :param fail: onlyOwner
        :param parameters: user, pause
        """
        if not parameters:
            parameters = {}
        if fail:
            parameters["user"] = parameters.get("user", self.RNG.choice(self.non_owner_users))
        else:
            parameters["user"] = parameters.get("user", "owner")
        parameters["pause"] = parameters.get("pause", self.RNG.choice([True, False]))

        user = parameters["user"]
        user_str = gen_user_str(user)
        pause = parameters["pause"]
        # end parameter instantiation

        if self.VERBOSE:
            s = gen_log("'About to call pause with parameters: " + str(parameters).replace("'", "") + "'")
        else:
            s = ""

        if pause:
            s += "await sale.pause(" + user_str + ");\n"
            self.paused = True
        else:
            s += "await sale.unpause(" + user_str + ");\n"
            self.paused = False

        if not fail:
            if pause:
                s += "await sale.pause(" + user_str + ");\n"
                s += "var is_paused = await sale.paused();\n"
                s += "assert(is_paused, 'sale should be paused after owner pauses it');"
                self.paused = True
            else:
                s += "await sale.unpause(" + user_str + ");\n"
                s += "var is_paused = await sale.paused();\n"
                s += "assert(!is_paused, 'sale should be unpaused after owner unpauses it');"
                self.paused = False
        else:
            if pause:
                s += self.onlyOwner("sale.pause", "only the owner can pause the crowd sale", parameters)
            else:
                s += self.onlyOwner("sale.unpause", "only the owner can unpause the crowd sale", parameters)
        return s;

    def terminate(self, fail=None, parameters=None):
        """
        :param fail: onlyOwner
        :param parameters: user
        """
        if not parameters:
            parameters = {}
        if fail:
            parameters["user"] = parameters.get("user", self.RNG.choice(self.non_owner_users))
        else:
            parameters["user"] = parameters.get("user", "owner")

        user = parameters["user"]
        # end parameter instantiation

        if self.VERBOSE:
            s = gen_log("'About to call terminate with parameters: " + str(parameters).replace("'", "") + "'")
        else:
            s = ""

        if not fail:
            # run as the owner
            user_str = gen_user_str(user)
            s += "await sale.terminate(" + user_str + ");\n"
            s += "var closed = await sale.saleClosed();\n"
            s += "assert(closed, 'sale should be closed after owner terminates it');"
            self.saleClosed = True
        else:
            s += self.onlyOwner("sale.terminate", "only the owner can terminate the crowd sale", parameters)
        return s;

    def ownerUnlockFund(self, fail=None, parameters=None):
        """
        :param fail: onlyOwner, afterDeadline
        :param parameters: user
        """
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

        if self.VERBOSE:
            s = gen_log("'About to call ownerUnlockFund with parameters: " + str(parameters).replace("'", "") + "'")
        else:
            s = ""

        if not fail:
            # run as the owner
            user_str = gen_user_str(user)
            s += "await sale.ownerUnlockFund(" + user_str + ");\n"
            s += "var goal_reached = await sale.fundingGoalReached();\n"
            s += "assert(goal_reached, 'fundingGoalReached should be false after calling, allowing users to withdraw');"
            self.saleClosed = True
        elif fail == "onlyOwner":
            s += self.onlyOwner("sale.ownerUnlockFund",
                                    "only the owner can unlock funds from the crowd sale",
                               parameters)
        elif fail == "afterDeadline":
            # TODO
            sys.exit("TODO afterDeadline")
        return s;


    def setRate(self, fail=None, parameters=None):
        """
        :param fail: onlyOwner, rateAbove, rateBelow
        :param parameters: user, rate
        """
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
            parameters["rate"] = parameters.get("rate", self.RNG.randint(self.low_rate, self.high_rate))

        user = parameters["user"]
        rate = parameters["rate"]
        user_str = gen_user_str(user)
        # end parameter instantiation

        if self.VERBOSE:
            s = gen_log("'About to call setRate with parameters: " + str(parameters).replace("'", "") + "'")
        else:
            s = ""

        if not fail:
            # run as the owner
            s += "await sale.setRate(" + str(rate) + ", " + user_str + ");\n"
            s += "var currentRate = await sale.rate();\n"
            s += gen_assert_equal("currentRate", rate, "the rate should be set to the new value")
            self.rate = rate
        elif fail == "onlyOwner":
            s += self.onlyOwner("sale.setRate", "only the owner can set the rate")
        elif fail == "rateAbove" or fail == "rateBelow":
            s += "await sale.setRate(" + str(rate) + ", " + user_str + ");\n"
            s = wrap_exception(s, "the new rate must be within the bounds")
        if fail:
            s += "var currentRate = await sale.rate();\n"
            s += gen_assert_equal("currentRate", self.rate, "the rate should not have changed")
        return s;

    def ownerSafeWithdrawal(self, fail=None, parameters=None):
        """
        :param fail: onlyOwner
        :param parameters: user
        """
        if not parameters:
            parameters = {}
        if fail == "onlyOwner":
            parameters["user"] = parameters.get("user", self.RNG.choice(self.non_owner_users))
        else:
            parameters["user"] = parameters.get("user", "owner")

        user = parameters["user"]
        user_str = gen_user_str(user)
        # end parameter instantiation
        if self.VERBOSE:
            s = gen_log("'About to call ownerSafeWithdrawal with parameters: " + str(parameters).replace("'", "") + "'")
        else:
            s = ""

        if fail == "onlyOwner":
            s += self.onlyOwner("sale.ownerSafeWithdrawal", "only the owner can can ownerSafeWithdrawal", parameters)
        elif not self.goal_reached:
            s += "await sale.ownerSafeWithdrawal(" + user_str + ");\n"
            s = wrap_exception(s, "cannot call ownerSafeWithdrawal before the goal is reached")
        elif not fail:
            s += "await sale.ownerSafeWithdrawal(" + user_str + ");\n"
            # assert that the contract ether balance is zero
            s = wrap_ether_balance_checks(s, "sale.address", "sale_ether")
            s = wrap_ether_balance_checks(s, "beneficiary", "beneficiary_ether")
            s += gen_log("beneficiary_ether_before")
            s += gen_log("beneficiary_ether_after")
            s += gen_log("sale_ether_before")
            s += gen_log("sale_ether_after")
            s += gen_log("'Check:'")
            s += "var test1 = await beneficiary_ether_before.plus(sale_ether_before);\n"
            s += "var test2 = await beneficiary_ether_after.plus(22);\n"
            #s += "var test1 = await test1;\n"
            #s += "var test2 = await test2;\n"
            s += gen_log("test1")
            s += gen_log("test2")
            s += gen_log("beneficiary_ether_before")
            s += gen_log("beneficiary_ether_after")

            s += gen_assert_equal("test1", "test2", "sale ether should be zero after ownerSafeWithdrawal")
            # assert that the beneficiary's ether balance is increased
            s += gen_assert_equal("beneficiary_ether_before.plus(sale_ether_before)",
                                  "beneficiary_ether_after.plus(1)",
                                  "the beneficiary should have gained the ether from the sale after ownerSafeWithdrawal")
            return s
            sys.exit("TODO ownerSafeWithdrawal")
        else:
            sys.exit("Missing case in ownerSafeWithdrawal")
        return s

    def ownerAllocateTokens(self, fail=None, parameters=None):
        """
        :param fail: belowMinContribution, validDestination
        :param parameters: user, wei
        """
        if not parameters:
            parameters = {}
        if fail == "onlyOwner":
            parameters["user"] = parameters.get("user", self.RNG.choice(self.non_owner_users))
        else:
            parameters["user"] = parameters.get("user", "owner")
        if fail == "validDestination":
            parameters["to_user"] = parameters.get("to_user", self.RNG.choice(self.bad_destinations))
        else:
            parameters["to_user"] = parameters.get("to_user", self.RNG.choice(self.non_owner_users))
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
        amount_mini_qsp = str(parameters["amount_mini_qsp"])
        amount_wei = str(parameters["amount_wei"])
        # end parameter instantiation

        if self.VERBOSE:
            s = gen_log("'About to call ownerAllocateTokens with parameters: " + str(parameters).replace("'", "") + "'")
        else:
            s = ""

        if not fail:
            s += "await sale.ownerAllocateTokens(" + \
                ", ".join([to_user, amount_wei, amount_mini_qsp, user_str]) + ");\n"
            # assert that token.balances[to_user] increases by amount_mini_qsp
            vid = "token_balance_" + to_user
            s = wrap_token_balance_checks(s, to_user, vid)
            s += balance_assertion_check(vid, ".add(" + gen_big_int(amount_mini_qsp) + ")",
                                         "the token balance of the to_user should increase after ownerAllocateTokens")

            # assert that the sale.balanceOf[to_user] increases by amount_wei
            vid = "sale_balance_" + to_user
            s = wrap_sale_balance_checks(s, to_user, vid)
            s += balance_assertion_check(vid, ".add(" + gen_big_int(amount_wei) + ")",
                                         "the sale balance of the to_user should increase after ownerAllocateTokens")

            # assert that the allowance of crowdsale decreases by amount_mini_qsp
            vid = "crowdsale_allowance"
            s = wrap_allowance_checks(s, "sale.address", vid)
            s += balance_assertion_check(vid, ".minus(" + gen_big_int(amount_mini_qsp) + ")",
                                         "the allowance of the crowdsale should decrease by amount_mini_qsp")

            # assert that the amountRaised field has increased
            vid = "amount_raised"
            s = wrap_amount_raised(s, vid)
            s += balance_assertion_check(vid, ".add(" + gen_big_int(amount_wei) + ")",
                                         "the amountRaised of the crowdsale should increase by amountWei in ownerAllocateTokens")

            # update the state of crowdsale
            self.update_state_with_purchase(to_user, amount_wei, amount_mini_qsp)

            # assert that the goalReached and capReached fields have changed if necessary
            s += goal_and_cap_assertion_checks(self.goal_reached, self.cap_reached)

        elif fail == "onlyOwner":
            s += self.onlyOwner("sale.ownerAllocateTokens",
                                    "only the owner can call ownerAllocateTokens",
                               parameters)
        elif fail == "validDestination":
            s += "await sale.ownerAllocateTokens(" + \
                ", ".join([to_user, amount_wei, amount_mini_qsp, user_str]) + ");\n"
            s = wrap_exception(s, "the to-address is not valid for allocating tokens")
        elif fail == "exceedAllowance":
            s += "await sale.ownerAllocateTokens(" + \
                ", ".join([to_user, amount_wei, amount_mini_qsp, user_str]) + ");\n"
            s = wrap_exception(s, "the amount of mini-QSP exceeds the crowdsale's allowance")
        if fail:
            s += "var currentCrowdSaleAllowance = await token.crowdSaleAllowance();\n"
            s += gen_assert_equal("currentCrowdSaleAllowance",
                                  self.token.crowdsale_allowance,
                                  "the crowdsale allowance should not have changed")
        return s;

    def fallback(self, fail=None, parameters=None):
        """
        :param fail: user, wei
        :param parameters: belowMinContribution, validDestination
        """
        if not parameters:
            parameters = {}
        if fail == "validDestination":
            parameters["user"] = parameters.get("user", self.RNG.choice(self.bad_destinations))
        else:
            parameters["user"] = parameters.get("user", self.RNG.choice(self.basic_users))
        if fail == "belowMinContribution":
            parameters["wei"] = parameters.get("wei", self.RNG.randint(0, int(0.1*ETHER - 1)))
        else:
            parameters["wei"] = parameters.get("wei", self.RNG.randint(int(0.1 * ETHER), ETHER))

        user = parameters["user"]
        wei = parameters["wei"]
        user_str = gen_user_str(user, wei)
        # end parameter instantiation

        if self.VERBOSE:
            s = gen_log("'About to call fallback with parameters: " + str(parameters).replace("'", "") + "'")
        else:
            s = ""

        s += "await sale.sendTransaction(" + user_str + ");\n"

        payable_disallowed = (self.cap_reached
              or self.saleClosed
              or self.paused
              or self.env.current_time < self.startTime
              or self.env.current_time > self.endTime)
        if not fail and not payable_disallowed:
            # assert that the balance of the user in token is increased (qsp = wei * rate)
            vid = "token_balance_" + user
            s = wrap_token_balance_checks(s, user, vid)
            s += balance_assertion_check(vid, ".add(" + gen_big_int(wei * self.rate) + ")",
                                         "the token balance of the user should increase after contributing")

            # assert that the balance of the user in sale is increased (wei)
            vid = "sale_balance_" + user
            s = wrap_sale_balance_checks(s, user, vid)
            s += balance_assertion_check(vid, ".add(" + gen_big_int(wei) + ")",
                                         "the sale balance of the user should increase after contributing")

            # assert that the amountRaised field has increased
            vid = "amount_raised"
            s = wrap_amount_raised(s, vid)
            s += balance_assertion_check(vid, ".add(" + gen_big_int(wei) + ")",
                                         "the amountRaised of the crowdsale should increase by wei")

            # assert that the allowance of the crowdsale has decreased
            vid = "crowdsale_allowance"
            s = wrap_allowance_checks(s, "sale.address", vid)
            s += balance_assertion_check(vid, ".minus(" + gen_big_int(wei * self.rate) + ")",
                                         "the allowance of the crowdsale should decrease by wei * rate")

            # update the state of crowdsale
            self.update_state_with_purchase(user, wei, None)

            # assert that the goalReached and capReached fields have changed if necessary
            s += goal_and_cap_assertion_checks(self.goal_reached, self.cap_reached)


        elif fail == "belowMinContribution":
            s = wrap_exception(s, "cannot contribute below the minimum")
        elif fail == "validDestination":
            s = wrap_exception(s, "the user is not allowed to purchase tokens")
        elif payable_disallowed:
            s = wrap_exception(s, "cannot contribute after the sale is beforeStart/closed/paused/finished")
        else:
            print("TODO finish payable")
            s = ""
        return s;

