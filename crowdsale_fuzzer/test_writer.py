
def wrap_exception(s, e):
    ret =  "try{\n"
    ret += "    flag = false;\n"
    ret += "    " + s + "\n"
    ret += "}\n"
    ret += "catch(e){\n"
    ret += "    flag = true;\n"
    ret += "}\n"
    ret += "if(!flag){ throw new Error(\"" + e + "\"); }\n"
    ret += "flag = false;\n"
    return ret

def wrap_token_balance_checks(s, user, var_name):
    ret =  "var " + var_name + "_before = await token.balanceOf(" + user + ")\n"
    ret += s
    ret += "var " + var_name + "_after = await token.balanceOf(" + user + ")\n"
    return ret

def wrap_ether_balance_checks(s, addr, var_name):
    ret =  "var " + var_name + "_before = await web3.eth.getBalance(" + addr + ")\n"
    ret += s
    ret += "var " + var_name + "_after = await web3.eth.getBalance(" + addr + ")\n"
    return ret

def balance_assertion_check(vid, left_operation, error_message):
    l = vid + "_before"
    r = vid + "_after"
    l += left_operation
    return gen_assert_equal(to_number(l), to_number(r), error_message)

def wrap_sale_balance_checks(s, user, var_name):
    ret =  "var " + var_name + "_before = await sale.balanceOf(" + user + ")\n"
    ret += s
    ret += "var " + var_name + "_after = await sale.balanceOf(" + user + ")\n"
    return ret

def wrap_amount_raised(s, var_name):
    ret =  "var " + var_name + "_before = await sale.amountRaised()\n"
    ret += s
    ret +=  "var " + var_name + "_after = await sale.amountRaised()\n"
    return ret

def wrap_allowance_checks(s, user, var_name):
    ret =  "var " + var_name + "_before = await token.allowance(" + "token_owner" + ", " + user + ")\n"
    ret += s
    ret += "var " + var_name + "_after = await token.allowance(" + "token_owner" + ", " + user + ")\n"
    return ret

def goal_and_cap_assertion_checks(goal_reached, cap_reached):
    # assert that the goalReached field has changed if necessary
    s = "var goal_reached = await sale.fundingGoalReached();\n"
    if goal_reached:
        s += "assert(goal_reached, 'the funding goal has been reached and should be true');\n"
    else:
        s += "assert(!goal_reached, 'the funding goal has not been reached and should be false');\n"

    # assert that the capReached field has changed if necessary
    s += "var cap_reached = await sale.fundingCapReached();\n"
    if cap_reached:
        s += "assert(cap_reached, 'the funding cap has been reached and should be true');\n"
    else:
        s += "assert(!cap_reached, 'the funding cap has not been reached and should be false');\n"
    return s

def gen_header(out):
    header = """
var QuantstampSale = artifacts.require("./QuantstampSale.sol");
var QuantstampToken = artifacts.require("./QuantstampToken.sol");
var QuantstampSaleMock = artifacts.require('./helpers/QuantstampSaleMock.sol');

// var bigInt = require("big-integer");
var bigInt = require('bignumber.js');

async function logUserBalances (token, accounts) {
    console.log("");
    console.log("User Balances:");
    console.log("--------------");
    console.log(`Owner: ${(await token.balanceOf(accounts[0])).toNumber()}`);
    console.log(`User1: ${(await token.balanceOf(accounts[1])).toNumber()}`);
    console.log(`User2: ${(await token.balanceOf(accounts[2])).toNumber()}`);
    console.log(`User3: ${(await token.balanceOf(accounts[3])).toNumber()}`);

    console.log("--------------");
    console.log("");
}

async function logEthBalances (token, sale, accounts) {
    console.log("");
    console.log("Eth Balances:");
    console.log("-------------");
    console.log(`Owner: ${(await web3.eth.getBalance(accounts[0])).toNumber()}`);
    console.log(`User1: ${(await web3.eth.getBalance(accounts[1])).toNumber()}`);
    console.log(`User2: ${(await web3.eth.getBalance(accounts[2])).toNumber()}`);
    console.log(`User3: ${(await web3.eth.getBalance(accounts[3])).toNumber()}`);
    console.log(`Sale : ${(await web3.eth.getBalance(sale.address)).toNumber()}`);
    console.log(`Token: ${(await web3.eth.getBalance(token.address)).toNumber()}`);

    console.log("--------------");
    console.log("");
}
    """
    out.write(header + "\n")


def gen_test_contract_header(out, params, seed):
    params = ", ".join([str(i) for i in params])
    s = "contract('Fuzz Test " + str(seed) + "', function(accounts) {\n"

    s += """
        var owner = accounts[0];
        var beneficiary = accounts[1];
        var token_admin = accounts[2];
        var user3 = accounts[3];
        var user4 = accounts[4];
        var flag = false;
        var time = new Date().getTime() / 1000;


        beforeEach(function() {
        return QuantstampToken.deployed().then(function(instance) {
            token = instance;
            return token.address;
        }).then(function(addr) {
            token_address = addr;
        """
    s += "    return QuantstampSaleMock.new(" + params + ", token_address);"
    s += """
        }).then(function(instance2){
            sale = instance2;
            return token.INITIAL_SUPPLY();
        }).then(function(val){
            initialSupply = val.toNumber();
            return sale.rate();
        }).then(function(val){
            rate = val.toNumber();
            return token_owner = token.owner()
        }).then(function(val){
            token_owner = val
        });
        });

"""
#    return QuantstampSale.deployed().then(function(instance) {

    out.write(s)

def check_value(var_name, expr, convert_to_number=False):
    s = "var " + var_name + " = await " + expr + ";\n"
    s += gen_log("'" + var_name + " = ' + " + (to_number(var_name) if convert_to_number else var_name))
    return s

def gen_test_contract_footer(out):
    out.write("});\n")

def gen_assert_equal(l, r, e):
    return "assert.equal(" + str(l) + ", " + str(r) + ", '" + e +"');\n"

def gen_log(e):
    return "console.log(" + e + ");\n"

def to_number(e):
    return e + ".toNumber()"

def gen_big_int(n):
    return "new bigInt(" + str(n) + ")"
