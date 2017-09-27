
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
    ret =  "let " + var_name + "_before = await token.balanceOf(" + user + ")\n"
    ret += s
    ret += "let " + var_name + "_after = await token.balanceOf(" + user + ")\n"
    return ret


def wrap_sale_balance_checks(s, user, var_name):
    ret =  "let " + var_name + "_before = await sale.balanceOf(" + user + ")\n"
    ret += s
    ret += "let " + var_name + "_after = await sale.balanceOf(" + user + ")\n"
    return ret

def wrap_allowance_checks(s, user, var_name):
    ret =  "let " + var_name + "_before = await token.allowance(" + "token_owner" + ", " + user + ")\n"
    ret += s
    ret += "let " + var_name + "_after = await token.allowance(" + "token_owner" + ", " + user + ")\n"
    return ret


def gen_header(out):
    header = """
var QuantstampSale = artifacts.require("./QuantstampSale.sol");
var QuantstampToken = artifacts.require("./QuantstampToken.sol");
var bigInt = require("big-integer");

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


def gen_test_contract_header(out, seed):
    s = "contract('Fuzz Test " + str(seed) + "', function(accounts) {\n"

    s += """
    var owner = accounts[0];
    var beneficiary = accounts[1];
    var user2 = accounts[2];
    var user3 = accounts[3];
    var flag = false;

    beforeEach(function() {
    return QuantstampSale.deployed().then(function(instance) {
        sale = instance;
        return QuantstampToken.deployed();
    }).then(function(instance2){
        token = instance2;
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

    out.write(s)

def gen_test_contract_footer(out):
    out.write("});\n")

def gen_assert_equal(l, r, e):
    return "assert.equal(" + str(l) + ", " + str(r) + ", '" + e +"');\n"

def gen_log(e):
    return "console.log(" + e + ");\n"

def to_number(e):
    return e + ".toNumber()"


def gen_big_int(n):
    return "bigInt(" + str(n) + ")"
