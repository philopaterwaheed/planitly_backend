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

app.post('/api/node/firebase_register', async (req, res) => {
	const { email, password } = req.body;

	try {
		const userCredential = await createUserWithEmailAndPassword(auth, email, password);
		await sendEmailVerification(userCredential.user);

		console.log('User registered:', userCredential.user.uid);
		res.status(201).json({
			message: 'User created. Verification email sent.',
			firebase_uid: userCredential.user.uid,
		});
	} catch (error) {
		console.error('Error during registration:', error);

		// Firebase Auth specific error handling
		switch (error.code) {
			case 'auth/email-already-in-use':
				return res.status(409).json({ error: 'username or email already exists' });
			case 'auth/invalid-email':
				return res.status(400).json({ error: 'Invalid email address.' });
			case 'auth/weak-password':
				return res.status(400).json({ error: 'Password is too weak.' });
			case 'auth/missing-password':
				return res.status(400).json({ error: 'Password is required.' });
			default:
				return res.status(500).json({ error: 'Internal Server Error.' });
		}
	}
});

app.listen(PORT, () => {
	console.log(`Server running on http://localhost:${PORT}`);
});
