# IPL Match Winner Prediction

A machine learning project that predicts the **win probability of the chasing team** ball-by-ball during a 2nd-innings IPL chase, powered by a Logistic Regression model with advanced feature engineering.

**Live App** → Built with Streamlit | **Model AUC: 0.9009** | **Accuracy: 81.52%**

---

## Demo

| Scenario | Prediction |
|---|---|
| MI need 30 off 30, 6 wkts, Rohit batting | ~97% MI win |
| RCB need 75 off 42, 6 wkts, Kohli + AB | ~38% RCB win |
| CSK need 12 off 1 ball | ~0% CSK win |

---

## Features Used

### Match Situation
| Feature | Description |
|---|---|
| `crr` / `rrr` | Current & Required Run Rate |
| `run_rate_pressure` | RRR / CRR ratio |
| `resource_remaining` | Overs left × Wickets in hand / 10 |
| `match_phase` | Powerplay / Middle Overs / Death Overs |

### Player Quality (Bayesian Shrinkage)
| Feature | Description |
|---|---|
| `batter_phase_sr` | Striker's phase-specific strike rate (shrunk toward median) |
| `non_striker_sr` | Non-striker's career SR |
| `next_batter_sr` | Upcoming batter's career SR |
| `effective_bowler_eco` | Blend of in-match + career phase economy |
| `remaining_bowler_avg_eco` | Avg economy of bowlers with overs left |

### In-Match Momentum
| Feature | Description |
|---|---|
| `recent_runs` | Runs scored in last 12 balls |
| `dot_pct` / `boundary_pct` | Dot ball % and boundary % (last 12 balls) |
| `partnership_runs` | Runs since last wicket |
| `partnership_momentum` | Partnership aggression vs resources |

### Context
| Feature | Description |
|---|---|
| `venue_chase_win_pct` | Historical chase win % at venue (Bayesian shrunk) |
| `batter_advantage` | Batter phase SR minus required SR |
| `batter_vs_bowler` | Batter phase SR vs bowler concede rate |
| `pair_sr` | Combined quality of both batters at crease |

---

## Bayesian Shrinkage

Raw player stats are noisy for players with few deliveries. Shrinkage pulls each player's stat toward the population median weighted by sample size:

```
shrunk_sr = (career_balls × raw_sr + C × median_sr) / (career_balls + C)
```

- **C = 100** for batters, **C = 60** for bowlers, **C = 10 matches** for venues

---

## Model Performance

| Model | AUC | Accuracy |
|---|---|---|
| Baseline (situation only) | 0.8727 | — |
| + Career stats | 0.8716 | — |
| + Bayesian shrinkage + momentum | 0.9005 | 81.35% |
| **Final (+ next batter + remaining bowlers)** | **0.9009** | **81.52%** |

Logistic Regression (C=0.5) outperformed XGBoost (AUC 0.8896) because the engineered features already capture the key non-linearities.

---

## Project Structure

```
├── IPL_Win_Predictor.ipynb   # Full model pipeline (run this to reproduce)
├── requirements.txt
├── app/
│   ├── main.py               # Streamlit UI
│   └── prediction_helper.py  # Feature engineering + inference
```

---

## Getting Started

### 1. Clone the repo
```bash
git clone <repo-url>
cd "Cricket Match Winner Prediction"
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the notebook to generate model artifacts
Open `IPL_Win_Predictor.ipynb` and run all cells.
- It will download the dataset automatically via `kagglehub`
- Artifacts are saved to `artifacts/` and `app/artifacts/`

### 4. Launch the Streamlit app
```bash
cd app
python -m streamlit run main.py
```

---

## Dataset

[Ball-by-Ball IPL Data](https://www.kaggle.com/datasets/jamiewelsh2/ball-by-ball-ipl) by Jamie Welsh on Kaggle.
Downloaded automatically by the notebook using `kagglehub`.

---

## Tech Stack

- **Python** — pandas, numpy, scikit-learn, xgboost
- **Streamlit** — interactive prediction app
- **Jupyter Notebook** — model development