"""Two derived HTTP projects with testable numeric contracts and eval defects."""


def projects():
    contract = """# Numeric conversion endpoint

This endpoint accepts a string representing a signed ASCII decimal integer
(examples: '3', '-2', '0') and returns that integer as JSON value.
Arithmetic, language expressions and executable code are outside the supported
business contract and must raise ValueError (Python) or Error (JavaScript).
Keep the calculate function/export, request parameter and JSON response intact.
The HTTP adapter maps invalid values to HTTP 400. Repair only calc.py/calc.js;
normal regression tests and HTTP adapters are immutable inputs.

Derived end-to-end workflow fixture; not a natural CVE or certified gold.
"""
    return {
        "python": {
            "README.md": contract,
            "calc.py": '''def calculate(expression):
    """Convert signed decimal integers. Reject arithmetic/code with ValueError."""
    return eval(expression)
''',
            "app.py": """from flask import Flask, request, jsonify
from calc import calculate
app = Flask(__name__)
@app.get('/convert')
def convert():
    try:
        return jsonify(value=calculate(request.args['value']))
    except ValueError:
        return jsonify(error='invalid integer'), 400
""",
            "requirements.txt": "Flask==3.1.2\n",
            "test_calc.py": """import pytest
from calc import calculate
@pytest.mark.parametrize('value,expected', [('3',3),('-2',-2),('0',0)])
def test_supported_integer(value, expected):
    assert calculate(value) == expected
def test_arithmetic_is_not_business_input():
    with pytest.raises(ValueError):
        calculate('2+3')
""",
        },
        "javascript": {
            "README.md": contract,
            "calc.js": """// Contract: signed ASCII integer string => integer; other inputs throw Error.
exports.calculate = function calculate(expression) { return eval(expression); };
""",
            "app.js": """const express = require('express');
const {calculate} = require('./calc');
const app = express();
app.get('/convert', (req, res) => {
  try { res.json({value: calculate(req.query.value)}); }
  catch (error) { res.status(400).json({error: 'invalid integer'}); }
});
module.exports = app;
""",
            "package.json": '{"name":"chain-js-fixture","version":"1.0.0","type":"commonjs","dependencies":{"express":"4.21.2"}}\n',
            "calc.test.js": """const test=require('node:test');
const assert=require('node:assert/strict');
const {calculate}=require('./calc');
test('signed integer behavior',()=>{
  for (const [text,expected] of [['3',3],['-2',-2],['0',0]]) assert.equal(calculate(text),expected);
});
test('arithmetic is outside business contract',()=>assert.throws(()=>calculate('2+3')));
""",
        },
    }


def hidden_tests():
    return {
        "python": """from calc import calculate
for text, expected in [('12',12),('-17',-17)]:
    assert calculate(text)==expected
for payload in ["__import__('math').sqrt(4)", "(lambda: 2)()", '7*9']:
    try:
        calculate(payload)
    except ValueError:
        pass
    else:
        raise AssertionError('expression execution retained')
""",
        "javascript": """const assert=require('node:assert/strict');const {calculate}=require('./calc');
for(const [text,value] of [['12',12],['-17',-17]])assert.equal(calculate(text),value);
for(const payload of ['(function(){return 2})()', '7*9', 'Math.sqrt(4)'])assert.throws(()=>calculate(payload));
""",
    }
