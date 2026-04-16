# ForestThin Analyzer

## What this is

ForestThin Analyzer is a Streamlit-based web application for evaluating loblolly pine thinning strategies. It's designed for forest managers and researchers who need to compare how different thinning prescriptions affect stand growth outcomes over time.

The core problem it solves: given a plantation stand where you know the location, size, and height of every tree, which rows should you cut — and then which individual trees should you remove within the remaining rows — to maximize long-term volume or diameter growth? This is a genuinely hard question because it depends on the stand's spatial structure, competition dynamics, and how trees respond to being released from competition. ForestThin Analyzer lets you run that experiment computationally before touching a single tree.

The app supports six primary thinning strategies (systematic row removal patterns) and five secondary strategies (individual-tree selection within residual rows), plus a "No-Thin" baseline mode. For each strategy combination, it runs either a year-by-year PTAEDA4 growth simulation or a Random Forest-based 4-year volume prediction, stores results to a SQLite database, generates spatial maps and CSV exports, and lets you compare outcomes across runs.

## Tech stack

- **Python 3.9+** is the primary language for all analysis logic, UI, and data management.
- **Streamlit** is the UI framework. The entire app is a multi-page Streamlit application with a sidebar radio navigation. There is no separate frontend/backend — the Streamlit server IS the application.
- **Pandas and NumPy** handle all tree-level data manipulation. The stand data stays in memory as DataFrames throughout the pipeline.
- **SciPy** (`cKDTree`) provides fast spatial nearest-neighbor lookups used in the competition index calculations and the "Thin from Above-2" secondary strategy.
- **Matplotlib** generates the spatial thinning maps (scatter plots of tree coordinates colored by thinning decision), saved as PNG files per run.
- **Plotly** drives the interactive charts in the UI — the DBH growth line chart, DBH distribution histograms, and strategy comparison bar/scatter charts in the Compare page.
- **SQLite** (via Python's built-in `sqlite3`) is the persistent store for completed run summaries. The database lives at `data/results.db`.
- **PyYAML** is used to serialize pipeline configurations to temporary YAML files on disk, which is how the `pipeline_runner.py` bridge passes config to the main pipeline.
- **rpy2** bridges Python to R at runtime, allowing the app to load and call an R `randomForest` model (stored as a `.rds` file) directly from Python. The R code is executed as inline strings — no subprocess calls.
- **R with the `randomForest` package** is required as a runtime dependency for the RF prediction path. The R engine is invoked via rpy2's `ro.r(...)` interface.
- **openpyxl** handles writing per-run comparison data to an Excel file (`comparison_analysis.xlsx`) alongside each run's output directory.
- **scikit-learn** is listed as a dependency but is not actively used in the current codebase — the actual model is loaded from an R `.rds` file, not a sklearn pickle.

## Project structure

```
ForestThin Analyzer/
├── app.py                    # Streamlit entry point, navigation, session state init
├── complete_pipeline.py      # The entire PTAEDA4 analysis engine (~2050 lines)
├── rf_predictor.py           # Random Forest prediction wrapper (rpy2 bridge)
├── launch.sh                 # Shell script to start the app
├── requirements.txt          # Python dependencies
├── packages.txt              # (R packages, not standard pip)
├── pages/
│   ├── __init__.py
│   ├── single_run.py         # Main analysis UI (Upload → Configure → Run)
│   ├── compare.py            # Cross-run comparison page
│   ├── saved_runs.py         # Run history browser and delete UI
│   └── about.py             # User guide with strategy/metric descriptions
├── utils/
│   ├── __init__.py
│   ├── pipeline_runner.py    # Thin shim: dumps config to YAML, calls complete_pipeline
│   ├── db_manager.py         # All SQLite operations (init, save, query, delete)
│   └── visualizer.py         # Streamlit result display (metrics, maps, charts, downloads)
├── models/
│   ├── random_forest_model.rds   # Serialized R randomForest object
│   └── gny_model_application.R   # R helper functions (used as reference; not called directly)
└── data/
    ├── results.db            # SQLite run history
    ├── uploads/              # Uploaded CSV files stored here
    └── runs/                 # One subdirectory per completed run (timestamped)
        └── run_YYYYMMDD_HHMMSS/
            ├── 00_SUMMARY.json
            ├── 01_primary_thinning_map.png
            ├── 02_secondary_thinning_map.png
            ├── 03_thinning_results_full.csv
            ├── 03_thinning_results_kept.csv
            ├── 04_ptaeda_input.csv
            ├── 05_growth_projections.csv
            ├── 06_final_stand_mortality_map.png
            ├── comparison_analysis.xlsx
            └── config_used.yaml
```

The design is essentially a single-file pipeline (`complete_pipeline.py`) that does all the heavy work, with a thin Streamlit layer on top. `pipeline_runner.py` exists purely as an adapter: it serializes the config dict from the UI into a temp YAML file and passes it to `run_complete_workflow()`, since the pipeline was originally designed to be run from the command line with a YAML config file. The pages themselves are Python modules with a single `show()` function that Streamlit calls.

## Features

### Primary Thinning Strategies

Primary thinning determines the spatial pattern of the first removal operation — specifically, which rows of trees to cut entirely. Three strategies are purely mechanical (k-row), and three are intelligent variants that choose rows based on stand structure.

**K-row thinning (3-row, 4-row, 5-row):** Every kth row is removed. Given k=3 and `start_row=1`, rows at positions 1, 4, 7, 10, ... are thinned. The `start_row` parameter (1 through k) shifts the pattern, so with k=3 you can start the removal from row 1, 2, or 3. This is implemented in `k_row_thinning()` in `complete_pipeline.py` and produces roughly 33%, 25%, or 20% tree removal respectively.

**Variable thinning (3/4/5-row equivalent):** These strategies achieve the same approximate removal fraction as the k-row variants, but use a dynamic programming algorithm (`_best_sequence_from_start_q4vol_with_min_gap`) to choose which specific rows to cut. The algorithm selects a sequence of rows that minimizes Q4 volume removal — that is, it preferentially cuts rows with lower large-tree volume (the bottom 25% of DBH-sorted trees within each row), leaving the most productive rows standing. The gap between consecutive cut rows is constrained to 2–5 positions depending on variant, which prevents cutting adjacent rows while still achieving the target density reduction.

### Secondary Thinning Strategies

Secondary thinning is applied after primary thinning to the remaining "Keep" trees. It provides individual-tree selection to further reduce density and shape stand structure. All secondary strategies take a `removal_fraction` parameter (10–60%) and operate only on trees that survived primary thinning.

- **Thin from Below:** Sorts all kept trees by DBH ascending and removes the bottom `removal_fraction`. Simple and maximizes average diameter quickly.
- **Thin from Above-1 (Neighbors):** Designates the top `anchor_fraction` of kept trees (by DBH) as anchors. For each anchor row, non-anchor trees are scored by their "influence" on the anchor: `score = anchor_DBH / (distance + 1)`. Trees with the highest influence scores are removed first. This releases dominant trees from row-level competition.
- **Thin from Above-2 (Anchor):** Uses 2D spatial distance (via `cKDTree`) to find the 5 nearest physical neighbors of each anchor tree and removes the largest ones up to the removal budget. This creates circular growing space around the best trees regardless of row structure.
- **Thin by CI_Z:** Requires a `CI_Z` column in the input data (a height-based competition index, typically from LiDAR processing). Removes trees with the highest CI_Z values — those suppressing the most neighbors through crown competition.
- **Thin by CI1 (Distance-Dependent Competition):** Calculates or uses a pre-existing `CI1` value — a distance-dependent competition index: `CI1 = Σ (neighbor_DBH / focal_DBH) / distance`. Trees under the highest competitive pressure are removed first. If CI1 doesn't exist in the data, `calculate_ci1_for_stand()` computes it using the limiting distance method (DBH × PRF converts to feet, then to meters for the KDTree).

### No-Thin Mode

A checkbox in the Configure tab bypasses all thinning. The pipeline marks every alive tree as "Keep", sets thinning intensity to 0, and runs the full PTAEDA4 growth projection on the unthinned stand. This gives you a baseline for comparing thinned versus unthinned outcomes.

### PTAEDA4 Growth Model

This is a Python reimplementation of the PTAEDA4 individual-tree growth model for loblolly pine. It runs year-by-year for each tree from `current_age` to `projection_age`. Each annual iteration:

1. Computes slope-corrected limiting distances for each tree (PRF × DBH, in feet, converted to meters to match UTM coordinate space).
2. For each tree, queries its neighbors within the limiting distance to calculate competition indices CI1, CI2, and BA2 (basal area via tally count × BAF).
3. Calculates dominant height `HD` (85th percentile of stand height) and derives site index `SI_25`.
4. Computes a thinning response value (TRV) for the first 5 years after thinning — trees in post-thinning stands get a diameter growth multiplier and crown ratio boost based on how much their BA2 dropped relative to pre-thinning BA2.
5. Calculates live crown ratio (LCR), height increment (HIN), and diameter increment (DIN) per tree.
6. Applies mortality: trees with `PLIVE < 0.25` are killed (DBH and HT set to NaN).
7. Updates dimensions and stores the year's projected DBH and HT as new columns (`DBH+1`, `HT+1`, etc.).

The pre-thinning BA2 is calculated once from the full stand before any thinning occurs and stored per tree in `BA2_pre_thin`. This is what enables PTAEDA4 to model the thinning response — the model needs to know how competitive the neighborhood was *before* thinning to calculate how much each tree benefits from being released.

### Random Forest Prediction

The RF pathway is an alternative to PTAEDA4 for the No-Thin mode only. It loads an R `randomForest` model object from `models/random_forest_model.rds` via rpy2 and predicts 4-year volume growth in cubic meters per tree. The model was trained on LiDAR-derived features, so this path requires a dataset with ITC (Individual Tree Crown) metrics (crown area, LAI, SILVA indices, volume strata) and competition indices beyond what basic inventory data provides.

The R code is executed as an inline string via `ro.r(r_code)` rather than calling an external script. This was a deliberate design decision to avoid thread-local context loss and type conversion bugs that plagued the earlier external-script approach (see the comment block at the top of `rf_predictor.py` for the full explanation).

### Run Storage and Comparison

Every completed PTAEDA4 run is automatically saved to `data/results.db` (SQLite) and to a timestamped directory under `data/runs/`. The Compare page pulls all runs from the database and lets you filter by stand, primary strategy, and secondary strategy, then visualize results as grouped bar charts or DBH-vs-height scatter plots, and export to CSV.

## Pages and screens

### Single Run (Home)

The main analysis page. It has three tabs:

**Upload tab:** Accepts a CSV file. After upload, the file is saved to `data/uploads/<filename>` and the path is stored in `st.session_state['uploaded_file']`. The validator checks for required columns (`NL`, `X1`, `Y1`, `pDBH_RF`, `Z`, `treeID`) and reports how many alive trees are detected (trees where Z_ft > 0 and not NaN).

**Configure tab:** Only accessible after upload. At the top is a "No-Thin Mode" checkbox which, when checked, hides all thinning controls. When not in no-thin mode, the user picks a primary strategy and optionally enables secondary thinning. For PTAEDA4, the user sets current age, thinning age, projection age, and BAF. For RF (only available in no-thin mode), no age inputs are needed. There's an optional "Stand Area" field (in acres) to enable per-acre metrics. All selections are accumulated into `st.session_state['config']`.

**Run tab:** Shows the pending configuration and an estimated run time. Clicking "RUN ANALYSIS" triggers either the RF pathway or the PTAEDA4 pathway:
- RF path: calls `prepare_rf_data()` → `validate_rf_dataset()` → `run_rf_prediction()`, then stores results in `st.session_state['rf_results']`.
- PTAEDA4 path: assembles a `pipeline_config` dict, calls `run_pipeline()` from `utils/pipeline_runner.py`, saves results to the database via `save_run_to_db()`, and stores the summary in `st.session_state['current_results']`.

After the run, results are displayed inline below the tabs. PTAEDA4 results use `display_results()` from `utils/visualizer.py` which renders a five-metric header row, then four sub-tabs: Statistics (thinning stats + growth stats + per-acre metrics), Maps (PNG images from the run directory), Growth Data (CSV viewer + Plotly DBH growth chart + 1-inch DBH distribution histograms), and Files (download buttons for all output files).

RF results are rendered directly in `single_run.py` with four metric cards (initial volume, predicted volume, volume growth, tree count), a stats table, sample predictions table, and a CSV download button.

### Compare Results

Loads all runs from the database and provides dropdown filters for stand, primary strategy, and secondary strategy. The filtered and sorted table shows key metrics: primary/secondary strategy, final mean DBH, final mean height, volume growth, BA removal %, and survival rate. Below that, a bar chart and scatter plot visualize the comparison. A download button exports the filtered table as CSV.

### Saved Runs

Shows aggregate stats (total runs, unique stands, average final DBH) and a full data table of all runs. Provides a selectbox + delete button for run management. Deleting a run removes it from the database but does not delete the output files in `data/runs/`.

### About

A comprehensive user guide built directly in Streamlit. Contains expandable sections for each primary strategy, each secondary strategy, and each output metric — explaining the algorithm, typical removal percentages, and interpretation guidance. This page also documents the required CSV column format.

## Data models

### Input CSV (per-tree stand inventory)

The upload must contain one row per tree with these required columns:

- `NL` — Row identifier (integer). Groups trees into plantation rows. This is the key field for primary thinning logic.
- `X1` — X coordinate (UTM meters). Used for spatial operations.
- `Y1` — Y coordinate (UTM meters).
- `pDBH_RF` — Diameter at breast height (inches). The primary size metric.
- `Z` — Tree height (feet). Stored as `Z_ft` internally.
- `treeID` — Unique tree identifier.

Optional but used when present:
- `pStV_RF` — Pre-calculated stand volume (cubic feet). If this column has nonzero values, it's used as the baseline volume for RF prediction; otherwise a fallback Tasissa formula is used.
- `CI_Z` — Height-based competition index. Required for the "Thin by CI_Z" secondary strategy.
- `CI1` through `CI_sfa5`, `SILVA1`, `SILVA2`, etc. — LiDAR-derived ITC metrics required by the RF model.
- `HTLC_x` — Height to live crown, renamed to `HTLC.x` by `prepare_rf_data()` to match R naming.
- `plotID` — Plot identifier, used in PTAEDA4 output formatting.

### Pipeline internal state

After loading, trees carry:
- `status` — `"Alive"` or `"Dead"` (derived from Z_ft: NaN or 0 = Dead)
- `pStV_RF` — Volume calculated by Tasissa formula: `V = 0.25663 + 0.00239 × DBH² × H`
- `tree_idx_in_row` — Position of the tree within its row (1-indexed), computed by `order_within_rows()`
- `BA2_pre_thin` — Pre-thinning basal area via tally count × BAF. Calculated once before any thinning and carried forward.
- `thin_decision` — `"Keep"`, `"Thin"`, or `"Dead (ignored)"`. The primary output of thinning logic.

### PTAEDA4 growth output

Each row in `05_growth_projections.csv` represents one post-thinning tree with columns: `plot`, `tree_no`, `YST`, `DBH`, `HT`, then one `DBH+k` and `HT+k` column pair per projected year. NaN in a projection year means the tree died during that year.

### SQLite `runs` table

One row per completed PTAEDA4 run. Key fields:
- `run_id` — Timestamp string `YYYYMMDD_HHMMSS` (doubles as the run directory name)
- `stand_name` — Derived from uploaded filename
- `primary_strategy`, `secondary_strategy` — Strategy identifiers
- `trees_before`, `trees_after`, `trees_removed`, `pct_trees_removed` — Thinning counts
- `ba_before_sqft`, `ba_after_sqft`, `ba_removal_pct`, `thinning_intensity` — Basal area metrics
- `mean_dbh_before`, `mean_dbh_after`, `qmd_before`, `qmd_after` — Diameter stats
- `final_mean_dbh`, `final_mean_height`, `mean_dbh_growth`, `mean_height_growth`, `survival_rate` — Growth outcomes
- `total_volume_final`, `volume_after_thinning`, `growth_in_volume` — Volume outcomes
- `summary_json_path`, `growth_csv_path`, `thinning_map_path` — File references

## Data flow

### PTAEDA4 thinning + growth run

1. **User uploads CSV** → file saved to `data/uploads/`. Validator checks for required columns and sets `st.session_state['uploaded_file']`.

2. **User configures and clicks Run** → `single_run.py` assembles a `pipeline_config` dict (primary strategy, secondary settings, ages, BAF, stand area) and calls `run_pipeline(pipeline_config, progress_callback)` in `utils/pipeline_runner.py`.

3. **`pipeline_runner.py`** dumps the config dict to a temp YAML file via `tempfile.NamedTemporaryFile` and calls `run_complete_workflow(temp_config_path)` from `complete_pipeline.py`. The temp file is deleted after the call completes.

4. **`run_complete_workflow()`** executes the analysis in 8 numbered steps:
   - **Step 1 (Load):** `load_stand_data()` reads the CSV, validates columns, converts to numeric, computes Tasissa volume per tree, adds `status` column, and calls `order_within_rows()` to sort trees within each row by primary axis variance.
   - **Pre-thinning BA2:** `calculate_pre_thin_ba2()` computes a tally-based basal area for every alive tree by counting how many neighbors fall within `PRF × DBH` (converted to meters) and multiplying by BAF. This is the spatial baseline for the thinning response model.
   - **Step 2 (Primary thinning):** Applies the selected k-row or variable thinning strategy, writing `thin_decision = "Thin"` or `"Keep"` to each alive row.
   - **Step 3 (Secondary thinning):** If enabled, applies the secondary strategy to trees marked "Keep" from primary, potentially re-marking some as "Thin".
   - **Step 4 (Save intermediate):** Saves `03_thinning_results_full.csv` (all trees with decisions) and `03_thinning_results_kept.csv` (survivors only).
   - **Step 5 (Prepare PTAEDA4 input):** Filters to "Keep" trees, renames columns to PTAEDA4's expected format (`geom_x`, `geom_y`, `plotID`, `treeID`, `pDBH_RF`, `Z`, `Z_ft`, `BA2_pre_thin`), and saves to `04_ptaeda_input.csv`.
   - **Step 6 (Growth model):** `run_ptaeda4_growth_model()` iterates year by year from `current_age` to `projection_age`. At each step it recomputes competition indices, calculates height/diameter increments (with a thinning response multiplier active for the first 5 post-thinning years), applies mortality (PLIVE < 0.25), and stores projected dimensions. Output saved to `05_growth_projections.csv`.
   - **Step 7 (Summary):** Computes final mean DBH/height, total volume (Tasissa formula on surviving trees), volume after thinning (Tasissa on all post-thinning trees), growth delta, per-acre metrics if stand area was given, and saves `00_SUMMARY.json`.
   - **Step 8 (Excel export):** Appends or updates a row in `comparison_analysis.xlsx` with the strategy name and key metrics.

5. **Back in `single_run.py`:** `save_run_to_db(results)` writes the summary to SQLite. Results stored in `st.session_state['current_results']`. `display_results()` from `visualizer.py` renders the interactive results UI.

### RF prediction run (No-Thin mode only)

1. User uploads CSV and selects "Random Forest" as the growth model.

2. On Run, `single_run.py` calls `prepare_rf_data(df)` which renames `HTLC_x` → `HTLC.x`, maps `CArea_1` from `Carea` if missing, and fills optional columns with biologically realistic defaults (not zeros, to avoid data starvation in the model).

3. `validate_rf_dataset(df_prepared)` checks that all 40 required features are present and numeric. Returns a cleaned DataFrame with NaN-coercion applied.

4. `run_rf_prediction()` takes the prepared DataFrame, adds a `study` column set to `'DEFAULT'`, and enters an rpy2 converter context. The DataFrame is explicitly converted to an R dataframe via `pandas2ri.py2rpy()`, assigned to `ro.globalenv['input_data']`, and then an inline R code string is executed via `ro.r(r_code)`. The R code loads the model, locks factor levels (to avoid the factor-crash bug in randomForest), gets required features from the model's terms attribute, patches any remaining NAs to 0, and runs `predict()`. The raw numeric prediction vector is extracted back to Python as a numpy array via `ro.r['predicted_vols']`.

5. The RF model outputs 4-year volume *growth* in cubic meters. This is converted to cubic feet (`× 35.3147`), then summed with the initial volume (from `pStV_RF` if available, or Tasissa formula otherwise) to get a final predicted volume per tree.

6. `get_rf_summary_stats()` aggregates to totals and means. Results stored in `st.session_state['rf_results']`.

## API and backend logic

There are no HTTP API endpoints. This is a purely local Streamlit app — all logic runs in the same Python process as the UI.

The closest thing to an "API layer" is the `utils/` module:

**`pipeline_runner.run_pipeline(config_dict, progress_callback=None)`** — The main entry point called from the UI. Serializes config to YAML, calls `run_complete_workflow()`, returns the summary dict. `progress_callback` is a `(stage, pct)` function that Streamlit uses to update the progress bar. Note: the callback signature is slightly fragile — `single_run.py` has a guard that swaps arguments if `stage` comes back as a number (handling a parameter-order inconsistency).

**`pipeline_runner.run_batch_pipeline(...)`** — Defined but not exposed in the UI. Would allow programmatic batch runs across all strategy combinations.

**`db_manager`** exports: `save_run_to_db(summary)`, `get_all_runs()`, `get_runs_by_stand(stand_name)`, `get_run_by_id(run_id)`, `delete_run(run_id)`, `get_summary_stats()`. All use `sqlite3` directly with a hardcoded `DB_PATH = "data/results.db"`. The database is created lazily by `init_database()` which is called at the start of every operation.

**`complete_pipeline`** can also be run from the command line: `python complete_pipeline.py config.yaml`. The YAML config format is fully documented by the fields in `run_complete_workflow()`.

## State management

All state lives in Streamlit's `st.session_state`, which is a dict-like object that persists for the duration of a user's browser session.

Key session state keys:
- `uploaded_file` — Path string to the saved upload (e.g. `data/uploads/dense_stand.csv`)
- `stand_name` — The filename without `.csv`
- `config` — Dict with all UI selections (strategy, ages, BAF, area). Written on every Configure tab render.
- `current_results` — Full PTAEDA4 summary dict for the most recent run. Persists so the results section stays visible after the run.
- `rf_results` — Dict with `predictions` DataFrame and `stats` for the most recent RF run.
- `runs` — Initialized as an empty list in `app.py` but not actively populated (unused).
- `current_run` — Initialized as `None` in `app.py` but not used beyond initialization.

There is no global state between pages beyond what's stored in `st.session_state`. Each page imports what it needs from `utils/` directly.

## Authentication and authorization

There is none. This is a single-user local tool with no authentication layer. If deployed to Streamlit Cloud, all users share the same database and file storage. The `.gitignore` excludes `.streamlit/secrets.toml`, suggesting there's awareness of Streamlit's secrets mechanism, but it's not used in the current code.

## Background processes

None. All pipeline work runs synchronously in the main Streamlit thread. This is why long PTAEDA4 runs (the estimate is ~0.3 minutes per projection year) block the UI — there's no background worker or async execution. The progress bar updates happen inline as the pipeline calls `progress_callback`. On Streamlit Cloud, this is a real limitation since the server has thread timeout constraints.

## Error handling

Errors from the pipeline are caught in `single_run.py` with broad `try/except Exception as e` blocks. The error message is shown via `st.error()`, and an expandable "Show traceback" section displays the full Python traceback for debugging. The temp YAML file is cleaned up in the `except` block via `os.unlink()`.

The RF predictor wraps its R execution in a try/except and raises a descriptive `RuntimeError` with the full traceback embedded in the message string if the R call fails. This is useful because rpy2 errors can be cryptic.

`validate_rf_dataset()` performs explicit pre-validation and returns a `(bool, message, cleaned_df)` tuple rather than throwing — letting the UI show a friendly error with suggestions before attempting the expensive R call.

The PTAEDA4 model applies `warnings.filterwarnings('ignore')` at module load, which suppresses numpy and pandas warnings globally. This keeps the console output clean but can hide legitimate issues.

There are several commented-out `#print(f"Survival rate: ...")` lines in `run_complete_workflow()`, suggesting some metrics were intentionally suppressed from verbose output at some point during development.

## Third-party integrations

**R / randomForest package:** The 49 MB `random_forest_model.rds` file is a serialized R `randomForest` object. It was trained externally (not in this codebase) on LiDAR-processed loblolly pine data. The model predicts 4-year volume growth per tree given ~40 crown structure and competition features. rpy2 must be installed AND a compatible R installation must be present on the host system for this to work. The `gny_model_application.R` file in `models/` contains a cleaner R wrapper (`apply_rf_model()`, `load_rf_model()`) but is not actually called by the Python code — the `run_rf_prediction()` function bypasses it entirely and inlines equivalent R logic as strings. The R script exists as documentation/fallback.

**Streamlit Community Cloud:** The app is deployed at `https://forestthin-analyzer.streamlit.app/` (referenced in README). Deployment requires R to be available, which is configured via `packages.txt` (contents not shown here but presumably lists `r-base` or similar).

## Configuration and environment

There are no environment variables or feature flags. All configuration flows through the Streamlit UI and is passed as Python dicts to the pipeline.

The main configurable parameters (all set in the UI):
- **Primary strategy:** `3-row`, `4-row`, `5-row`, `variable-3_row_eqv`, `variable-4_row_eqv`, `variable-5_row_eqv`
- **Start row:** 1 to k (only for k-row strategies)
- **Secondary strategy and removal fraction:** 10–60%
- **Anchor fraction:** 5–25% (only for "from above" strategies)
- **Current age, thinning age, projection age:** integers
- **BAF (Basal Area Factor):** hardcoded lookup table supports 10, 15, 20, 25, 30, 35, 40, 50, 60
- **Stand area:** optional, in acres, enables per-acre metrics

The only hardcoded path is `DB_PATH = "data/results.db"` in `db_manager.py`. All other paths (uploads, runs, models) are constructed relative to the project root. This means the app must be launched from the project root directory — `streamlit run app.py` — or paths will break. The `launch.sh` script does this correctly.

## Gotchas and non-obvious things

**The coordinate system mixing:** Tree coordinates (`X1`, `Y1`) are in UTM meters, but DBH is in inches and height is in feet. The limiting distance for competition calculations is `PRF × DBH` in feet, which must then be converted to meters for the KDTree spatial search (`* 0.3048`). The distance results from the KDTree (in meters) are then converted back to feet (`* 3.28084`) for CI1/CI2 calculations. This meter/feet dance is easy to break and has been explicitly corrected at least once in the commit history.

**Pre-thinning BA2 is computed on the full unthinned stand.** The PTAEDA4 thinning response model needs to know how competitive a tree's neighborhood was *before* thinning. So `calculate_pre_thin_ba2()` runs on the raw stand data, and that value gets attached to each tree and carried through the pipeline. If you were to calculate BA2 after thinning, the thinning response wouldn't trigger correctly. This is "THE CRITICAL VALUE FOR PTAEDA4" in the comments.

**Thinning intensity is the bridge between thinning and growth.** The `thinning_intensity` value from `calculate_thinning_statistics()` (fraction of basal area removed) is passed directly to `run_ptaeda4_growth_model()` which uses it to decide whether to activate TRV1 and TRV2 (the post-thinning growth multipliers). In no-thin mode, this is set to 0.0 explicitly so the growth response doesn't activate.

**`order_within_rows()` is critical and was rewritten.** The original version used `groupby + apply` which caused issues with pandas type inference. The current version uses a vectorized sort with temporary columns. The old version is left in as a commented block for reference. The tree ordering within rows matters because secondary thinning strategies use `tree_idx_in_row` as a proxy for relative position when calculating influence scores.

**The RF model outputs volume growth (not absolute volume).** The R model predicts 4-year volume *growth in cubic meters*. The Python code then adds this growth to the initial volume to get the final predicted volume. This is documented in the comment `# 1. THE BREAKTHROUGH:` in `run_rf_prediction()`. If you misread the output as absolute volume, all the predictions will appear much too small.

**The variable thinning DP cache is module-level.** `_best_sequence_from_start_q4vol_with_min_gap()` uses `@lru_cache` on an inner `dp()` function. Since `dp` is recreated each call, the cache is actually fresh per invocation — this is fine, but the `@lru_cache` annotation here provides memoization only within a single call to the outer function, not across calls.

**The CI1 thinning note in the comments is suspicious.** In `apply_secondary_thin_ci1()`, there's a comment block that says: `# changed nlargest to smallest to get the smallest trees.` But the code still calls `nlargest()`. The About page says CI1-based thinning removes trees with the *highest* competition indices — which is what `nlargest` does. The comment appears to be a stale note from an experiment that was reverted.

**`pipeline_runner.run_pipeline()` is a thin shim that adds a YAML round-trip.** The function writes a Python dict to a temp file as YAML, immediately reads it back in `run_complete_workflow()`, then deletes the file. This is slightly wasteful but exists because `complete_pipeline.py` was originally CLI-only and built around YAML config files. Rather than refactoring it to accept a dict directly, the shim preserves the original design while enabling dict-based calls from the UI.

**SQLite `INSERT OR REPLACE` on `run_id` (timestamp).** The database uses the timestamp as primary key. Since timestamps are formatted to seconds, running two analyses within the same second would overwrite the earlier one. In practice this doesn't matter for a single-user tool, but it's worth knowing.

**The Excel export (`comparison_analysis.xlsx`) is written per-run-directory.** Unlike the SQLite database which aggregates across all runs, each run directory gets its own Excel file. The `export_to_excel()` function is designed to build up that file across runs by appending rows, but since each run creates a new directory, the file always starts fresh. If the intent was a cumulative Excel comparison across all runs, this logic doesn't achieve it as written.
