import express from 'express'; 
import { auth } from './fire/Config.js';
import bodyParser from 'body-parser'; 
import dotenv from 'dotenv';
import { 
  createUserWithEmailAndPassword, 
  sendEmailVerification 
} from 'firebase/auth';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(bodyParser.json());

app.post('/firebase_register', async (req, res) => {
  const { email, password } = req.body;

  try {
    // Create user using Firebase Auth
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    
    // Send verification email to the user
    await sendEmailVerification(userCredential.user);
    
    res.status(201).json({
      message: 'User created. Verification email sent.',
    });
  } catch (error) {
    console.error('Error during registration:', error);
    res.status(400).json({ error: error.message });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
