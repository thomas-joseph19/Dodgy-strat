# NinjaTrader Setup Guide

Complete setup instructions for the Python ↔ NinjaTrader live trading bridge.
Follow every step in order — do this on a Sim account first.

---

## 1. Install NinjaTrader 8

Download from https://ninjatrader.com/trading-software/download/
Install and open it.  You do not need to pay — the free version supports live
trading through a connected broker.

---

## 2. Connect NinjaTrader to your MyFundedFutures account

MFFU uses Rithmic as its broker.  NT8 connects to Rithmic natively.

1. In NT8: **Tools → Accounts → Connect to broker**
2. Select **Rithmic** from the broker list
3. Enter the credentials MFFU emailed you after account activation
   - User, Password, and the Rithmic server URL (something like `rituz00XXX.rithmic.com`)
4. Click Connect — you should see your account appear in the Accounts panel
5. Verify the NQ futures instrument is visible under **Instruments**

MFFU support: https://help.myfundedfutures.com/en/articles/8528337-connecting-to-different-platforms-at-mffu

---

## 3. Install the NinjaScript strategy

### Option A — Copy the file (easiest)

1. Copy `PythonSignalStrategy.cs` to:
   ```
   C:\Users\<YourName>\Documents\NinjaTrader 8\bin\Custom\Strategies\
   ```
2. In NT8: **Tools → NinjaScript Editor**
3. In the editor toolbar: **Build → Build NinjaScript Assembly** (or press F5)
4. The output panel at the bottom should say "Build succeeded"
5. If there are red errors, screenshot them and check the NT8 forum

### Option B — Import through the editor

1. **Tools → NinjaScript Editor**
2. **File → Open** → navigate to `PythonSignalStrategy.cs`
3. The editor will copy it to the Strategies folder automatically
4. Press F5 to compile

---

## 4. Install Python dependencies

```
cd dodgy
pip install -r requirements.txt
```

If you want `.env` file support:
```
pip install python-dotenv
```

---

## 5. Create a .env file

In the `dodgy/` folder, create a file called `.env`:

```
NINJA_HOST=127.0.0.1
NINJA_PORT=6789
RITHMIC_CONTRACTS=1
MAX_DAILY_LOSS=-2000
```

Keep `RITHMIC_CONTRACTS=1` until you have verified the strategy works correctly.

`MAX_DAILY_LOSS` is the **Prop Firm Safety Guard** — the bridge will refuse all
new signals once your daily realized P&L drops below this threshold (in USD).
Set this to match your funded account's daily loss limit (MFFU default: -$2,000
for most eval accounts).  The guard resets automatically at midnight ET.

---

## 6. First run — Simulation mode (DO THIS FIRST)

### Step 6a — Start Python

```
cd dodgy
python -m live.run_live
```

You should see:
```
Waiting for NinjaTrader on 127.0.0.1:6789 …
  → Start PythonSignalStrategy on your NQ chart in NinjaTrader.
```

Leave this terminal open.

### Step 6b — Open an NQ chart in NinjaTrader

1. **New → Chart**
2. Instrument: **NQ 06-25** (or whatever the current front-month is — see below)
3. Bar period: **1 Minute**
4. Click OK

### Step 6c — Attach the strategy in Simulation mode

1. Right-click the chart → **Strategies → Add Strategy**
2. Find **PythonSignalStrategy** in the list
3. Configure:
   - PythonHost: `127.0.0.1`
   - PythonPort: `6789`
   - Contracts: `1`
   - **Account: select your SIM account** (not your live MFFU account yet)
4. Click **OK** then **Enable**

You should see in the Python terminal:
```
NinjaTrader connected from 127.0.0.1:XXXXX
```

And NT should start printing bars in its strategy log (right-click chart →
**Strategies → Strategy Properties → Log** tab, or check **Control Center →
Log**).

### Step 6d — Watch for signals

The strategy will run silently until a signal fires (ORB from 8:10–11:00 ET
or Dodgy from 12:00–16:00 ET).  Use the NinjaTrader **Control Center → Log**
to see the `[PythonSignal]` print messages.

---

## 7. Go live — Real account

Once you have verified paper trading for at least one full week:

1. Stop the strategy (right-click chart → **Strategies → Disable**)
2. Re-add the strategy but select your **MFFU live account** instead of Sim
3. Confirm in the MFFU dashboard that orders appear correctly

---

## 8. Rolling the front-month contract

NQ futures expire quarterly: **March (H), June (M), September (U), December (Z)**.
The rollover date is typically the **second Thursday of the expiry month**.

Before rollover:
1. Identify the new contract (e.g. NQM5 → NQU5)
2. Disable the strategy
3. Change the chart instrument to the new contract
4. Re-enable the strategy

You do not need to change any code — the chart drives the instrument.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Could not connect to Python" in NT log | Start `python -m live.run_live` first |
| No bars arriving in Python | Check NT strategy is Enabled and bar period is 1 Minute |
| Orders fire but don't fill | Verify your MFFU account is connected (green in Accounts panel) |
| "Build failed" in NinjaScript editor | Check the error lines — often a missing `using` or stray character |
| GEX fetch fails at day open | yfinance rate-limited; safe to ignore — Dodgy runs without GEX levels |
| Strategy stops after an NT disconnect | Disable and re-enable the strategy; restart Python if needed |
