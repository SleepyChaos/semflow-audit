const express = require('express');
const app = express();
app.get('/calculate', (req, res) => {
  res.send(String(eval(req.query.expression)));
});
app.listen(3000);
