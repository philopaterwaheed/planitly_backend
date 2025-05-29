import express from 'express';
import { auth } from './fire/Config.js';
import bodyParser from 'body-parser';
import dotenv from 'dotenv';
import {
	createUserWithEmailAndPassword,
	sendEmailVerification,
	signInWithEmailAndPassword,
	sendPasswordResetEmail
} from 'firebase/auth';

dotenv.config();
const app = express();
const PORT = process.env.PORT || 3000;
const AUTH_API_KEY = process.env.AUTH_API_KEY || "default_AUTH_api_key";

app.use(bodyParser.json());

app.use((req, res, next) => {
    const key = req.headers['auth_api_key'] || req.query.AUTH_API_KEY;
    if (!key || key !== AUTH_API_KEY) {
        return res.status(403).json({ error: 'Forbidden: Invalid API key.' });
    }
    next();
});

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

// Firebase Forget Password Route
app.post('/api/node/firebase_forgot-password', async (req, res) => {
	const { email } = req.body;

	try {
		if (!email) {
			return res.status(400).json({ error: 'Email is required.' });
		}

		// Send password reset email using Firebase
		await sendPasswordResetEmail(auth, email);

		console.log('Password reset email sent to:', email);
		res.status(200).json({ message: 'Password reset email sent successfully.' });
	} catch (error) {
		console.error('Error during password reset:', error);

		// Firebase Auth specific error handling
		switch (error.code) {
			case 'auth/user-not-found':
				return res.status(404).json({ error: 'User with this email does not exist.' });
			case 'auth/invalid-email':
				return res.status(400).json({ error: 'Invalid email address.' });
			default:
				return res.status(500).json({ error: 'Internal Server Error.' });
		}
	}
});
app.post('/api/node/firebase_login', async (req, res) => {
	const { email, password } = req.body;

	try {
		if (!email || !password) {
			return res.status(400).json({ error: 'Email and password are required.' });
		}

		const userCredential = await signInWithEmailAndPassword(auth, email, password);

		console.log('User logged in:', userCredential.user.uid);
		res.status(200).json({
			message: 'Login successful.',
			firebase_uid: userCredential.user.uid,
			email_verified: userCredential.user.emailVerified,
		});
	} catch (error) {
		console.error('Error during login:', error);

		switch (error.code) {
			case 'auth/user-not-found':
				return res.status(404).json({ error: 'User with this email does not exist.' });
			case 'auth/wrong-password':
				return res.status(401).json({ error: 'Incorrect password.' });
			case 'auth/invalid-email':
				return res.status(400).json({ error: 'Invalid email address.' });
			case 'auth/invalid-credential':
				return res.status(400).json({ error: 'Wrong password' });
			default:
				return res.status(500).json({ error: 'Internal Server Error.' });
		}
	}
});
app.listen(PORT, () => {
	console.log(`Server running on http://localhost:${PORT}`);
});
