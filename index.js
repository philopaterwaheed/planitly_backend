const express = require('express');
const app = express();

app.get('/api/node', (req, res) => {
  res.json({ message: 'Hello from Express.js' });
});

// For local development
if (require.main === module) {
  const PORT = 3000;
  app.listen(PORT, () => {
    console.log(`Express server running on port ${PORT}`);
  });
}

// Export for Vercel serverless functions
module.exports = app;
