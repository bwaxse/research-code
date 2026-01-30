# nc3/

N3C RECOVER Long COVID phenotyping algorithm adapted for _All of Us_.

## Key Files

**B.05b N3C RECOVER RF (Original).py**: XGBoost ML algorithm
- Identifies PASC/Long COVID patients using machine learning
- Originally developed in PySpark, adapted to pandas for _All of Us_ Workbench
- Published methodology from [Pfaff et al., 2022](https://pubmed.ncbi.nlm.nih.gov/35589549/)

## Algorithm Requirements

**Inclusion criteria:**
- COVID-positive diagnosis (condition_occurrence or lab result)
- At least 145 days since COVID index date
- At least one healthcare encounter between days 45-300 post-COVID
- Sufficient medication or diagnostic data for feature generation

**Key steps:**
1. Identify COVID-positive cohort from EHR conditions and lab results
2. Extract medication and diagnostic features
3. Apply pre-trained XGBoost model to predict Long COVID probability
4. Generate probability distribution and demographic characteristics

## Workflow Pattern

1. Install required libraries: `xgboost`, `scikit-learn`
2. Query OMOP CDR for COVID-positive participants
3. Build feature matrix from medications and diagnoses
4. Load pre-trained model weights (if available) or train new model
5. Generate predictions and validate cohort characteristics
6. Apply count censoring (< 20 rule) to all demographic summaries

## Important Notes

- Model was initially trained on C2022Q2R2 (v6) CDR - may need recalibration for newer versions
- Feature engineering is critical - medication and diagnosis codes must match training data
- All demographic stratification must follow < 20 count rules
- Document probability threshold used for Long COVID classification
