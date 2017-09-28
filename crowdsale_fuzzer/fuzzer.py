import os
import random
import sys

import test_writer
from solidity_entities.crowdsale import CrowdsaleFuzzer
from solidity_entities.environment import SolidityEnvironment
from solidity_entities.token import Token
from test_writer import gen_header, gen_test_contract_header, gen_test_contract_footer


# ==================== Change these parameters as needed. =============================
VERBOSE = True

START_TIME = 1323244
DURATION_IN_MINUTES = 2
CROWDSALE_PARAMETERS = ["owner", "beneficiary", "token_admin", 10, 20, 1, START_TIME, DURATION_IN_MINUTES, 5000]
CROWDSALE_CONTRACT_PARAMETERS = ["beneficiary", 10, 20, 1, START_TIME, DURATION_IN_MINUTES, 5000]
USERS = ["owner", "beneficiary", "token_admin", "user3", "user4"]

# TOKEN_PARAMETERS
DECIMALS = 18
INITIAL_SUPPLY = 1000000000 * (10 ** DECIMALS)
INITIAL_CROWDSALE_ALLOWANCE = 650000000 * (10 ** DECIMALS)
INITIAL_ADMIN_ALLOWANCE = 350000000 * (10 ** DECIMALS)

MAIN_TEST_DIR = "/home/ezulkosk/quantstamp/token-distribution/test/fuzz_tests/"

# test subtype directories
SUB_TEST_DIR = MAIN_TEST_DIR  # + "sale_terminate/"

RANDOM_SEED = 123
# =====================================================================================

RNG = random.Random()


def seed_random():
    global RANDOM_SEED
    global RNG
    if not RANDOM_SEED:
        RANDOM_SEED = random.randrange(sys.maxsize)
    RNG = random.Random(RANDOM_SEED)


def gen_test(out, ops=2):
    env = SolidityEnvironment()
    token = Token(INITIAL_SUPPLY, INITIAL_CROWDSALE_ALLOWANCE, INITIAL_ADMIN_ALLOWANCE)
    crowdsale = CrowdsaleFuzzer(RNG, env, token, USERS, *CROWDSALE_PARAMETERS)
    functions = crowdsale.functions
    functions = [i for i in functions if i.function.__name__ == "fuzz_terminate"]

    test_writer.gen_test_case_header(out)
    count = 0
    while count < ops:
        # get a function to test at random
        f = RNG.choice(functions)
        fail = RNG.choice(f.failure_types() + [None])
        s = f.function(fail)
        if not s:
            continue

        arr = s.split("\n")
        for line in arr:
            out.write("        " + line + "\n")
        count += 1
    out.write("    });\n")


def gen_predefined_test(out):
    env = SolidityEnvironment()
    token = Token(INITIAL_SUPPLY, INITIAL_CROWDSALE_ALLOWANCE, INITIAL_ADMIN_ALLOWANCE)
    c = CrowdsaleFuzzer(RNG, env, token, USERS, *CROWDSALE_PARAMETERS, VERBOSE)

    ops = [
        c.fallback(fail=None, parameters={"user": "user3", "wei": 0.2 * 10 ** 18}),
        c.owner_allocate_tokens(None, parameters={"amount_wei": int(0.2 * 10 ** 18)}),
        c.set_rate(None),
        c.check_time(),
        c.change_time(0),
        c.check_time(),
        c.fallback(fail=None, parameters={"user": "user3", "wei": 0.2 * 10 ** 18}),
        c.terminate(fail=None),
        c.fallback(fail=None, parameters={"user": "user3", "wei": 0.2 * 10**18}),
        test_writer.gen_log("'before new crowdsale'"),
        test_writer.check_value("old_contract_amount_raised", "sale.amountRaised()"),

        c.create_new_crowdsale(CROWDSALE_CONTRACT_PARAMETERS),
        test_writer.check_value("new_contract_amount_raised", "sale.amountRaised()"),
        test_writer.gen_log("'Finished Test'")
    ]

    test_writer.gen_test_case_header(out)
    count = 0
    for s in ops:
        if not s:
            continue

        arr = s.split("\n")
        for line in arr:
            out.write("        " + line + "\n")
        count += 1
    out.write("    });\n")


def main():
    seed_random()
    if not os.path.exists(SUB_TEST_DIR):
        os.makedirs(SUB_TEST_DIR)
    out_file = SUB_TEST_DIR + "/fuzz_test." + str(RANDOM_SEED) + ".js"
    with open(out_file, 'w') as out:
        gen_header(out)
        gen_test_contract_header(out, CROWDSALE_CONTRACT_PARAMETERS, RANDOM_SEED)
        gen_predefined_test(out)
        gen_test_contract_footer(out)
    print(out_file)


if __name__ == '__main__':
    main()
