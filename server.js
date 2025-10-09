// server.js
import express from 'express';
import cors from 'cors';
import { createClient } from '@supabase/supabase-js';
import 'dotenv/config';
// 🔑 Supabase credentials (service_role key stays server-side)
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SECRET = process.env.SUPABASE_SECRET; // do NOT expose in frontend
const supabase = createClient(SUPABASE_URL, SUPABASE_SECRET);

const app = express();
app.use(cors()); // allow requests from GitHub Pages
const PORT = process.env.PORT || 5000;

app.get('/api/feed', async (req, res) => {
	try {
		let dt = req.query.date;
		let player = req.query.player;
		if (!dt) {
			dt = new Date().toISOString().split('T')[0];
		}

		let data, error;
		if (player) {
			({ data, error } = await supabase.from('Feed').select('*').eq('player', player));
		} else {
			({ data, error } = await supabase.from('Feed').select('*').eq('dt', dt));
		}

		if (error) {
			console.error(error);
			return res.status(500).json({ error: error.message });
		}

		res.json(data);
	} catch (err) {
		console.error(err);
		res.status(500).json({ error: 'Server error' });
	}
});

app.get("/api/dingersEV", async (req, res) => {
	try {
		
	} catch (err) {
		console.error(err);
		res.status(500).json({ error: 'Server error' });
	}
});

app.listen(PORT, () => {
	console.log(`✅ API running on http://localhost:${PORT}`);
});
