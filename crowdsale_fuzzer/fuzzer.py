import os
import random
import sys


# TODO: change start variable somehow
# beneficiary, goal, cap, minContrib, start, duration, rate
from solidity_entities.crowdsale import CrowdsaleFuzzer
from solidity_entities.environment import SolidityEnvironment
from solidity_entities.function import Function
from solidity_entities.token import Token
from test_writer import gen_header, gen_test_contract_header, gen_test_contract_footer


# ==================== Change these parameters as needed. =============================

CROWDSALE_PARAMETERS = ["owner", "beneficiary", 10, 20, 1, 0, 123123123123, 5000]
USERS = ["owner", "beneficiary", "user2", "user3"]

# TOKEN_PARAMETERS
DECIMALS = 18
INITIAL_SUPPLY = 1000000000 * (10 ** DECIMALS);
INITIAL_CROWDSALE_ALLOWANCE = 650000000 * (10 ** DECIMALS);
INITIAL_ADMIN_ALLOWANCE = 350000000 * (10 ** DECIMALS);

MAIN_TEST_DIR = "/home/ezulkosk/quantstamp/token-distribution/test/fuzz_tests/"

# test subtype directories
SUB_TEST_DIR = MAIN_TEST_DIR # + "sale_terminate/"

# =====================================================================================



RANDOM_SEED=None
RNG = random.Random()
BOOLS = [True, False]

def seed_random():
    global RANDOM_SEED
    global RNG
    # RANDOM_SEED = 123
    RANDOM_SEED = random.randrange(sys.maxsize)
    RNG = random.Random(RANDOM_SEED)



def gen_test(out, ops=2):
    env = SolidityEnvironment()
    token = Token(INITIAL_SUPPLY, INITIAL_CROWDSALE_ALLOWANCE, INITIAL_ADMIN_ALLOWANCE)
    crowdsale = CrowdsaleFuzzer(RNG, env, token, USERS, *CROWDSALE_PARAMETERS)
    functions = crowdsale.functions
    functions = [i for i in functions if i.function.__name__ == "fuzz_fallback"]
    print(functions)

    out.write("it('should pass the fuzz test', async function(){\n")
    # TODO: clean this, need this line to initiate the crowdsale
    out.write("        await token.setCrowdsale(sale.address, 0);\n")
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


def main():
    seed_random()
    if not os.path.exists(SUB_TEST_DIR):
        os.makedirs(SUB_TEST_DIR)
    out_file = SUB_TEST_DIR +"/fuzz_test." + str(RANDOM_SEED) + ".js"
    with open(out_file, 'w') as out:
        gen_header(out)
        gen_test_contract_header(out, RANDOM_SEED)
        gen_test(out, ops=2)
        gen_test_contract_footer(out)
    print(out_file)




if __name__ == '__main__':
    main()