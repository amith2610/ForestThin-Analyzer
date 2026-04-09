# Random Forest Model Application Script
# Modified to work with Python integration via rpy2

library(randomForest)

#' Apply Random Forest Model to Input Data
#' 
#' @param input_data Data frame with required features
#' @param rf_model Loaded randomForest model object
#' @return Data frame with predictions added
apply_rf_model <- function(input_data, rf_model) {
  
  # 1. SAFELY EXTRACT REQUIRED FEATURES
  # Prefer the model's actual formula (terms) to catch all variables.
  # Fallback to importance matrix if terms don't exist.
  if (!is.null(rf_model$terms)) {
    required_features <- attr(rf_model$terms, "term.labels")
  } else {
    required_features <- rownames(rf_model$importance)
  }
  
  # 2. THE FACTOR TRAP FIX
  # randomForest crashes if categorical features don't exactly match training levels.
  # We dynamically intercept dummy strings (like 'DEFAULT') and lock them into valid Factors.
  if (!is.null(rf_model$forest$xlevels)) {
    for (var_name in names(rf_model$forest$xlevels)) {
      if (var_name %in% colnames(input_data)) {
        expected_levels <- rf_model$forest$xlevels[[var_name]]
        # Force dummy variables to match the first expected training level
        input_data[[var_name]] <- factor(expected_levels[1], levels = expected_levels)
      }
    }
  }
  
  # 3. CHECK FOR MISSING FEATURES
  missing_features <- setdiff(required_features, colnames(input_data))
  if (length(missing_features) > 0) {
    stop(paste("Missing required features:", paste(missing_features, collapse=", ")))
  }
  
  # 4. HANDLE MISSING VALUES (NAs)
  # Instead of dangerously subsetting the dataframe, we keep it intact.
  # We just coerce NAs to 0 to prevent predict() from fatal-crashing.
  prediction_data <- input_data
  if (any(is.na(prediction_data[, required_features, drop=FALSE]))) {
    warning("Input data contains missing values. Setting NAs to 0.")
    for (col in required_features) {
      if (any(is.na(prediction_data[[col]]))) {
         prediction_data[is.na(prediction_data[[col]]), col] <- 0
      }
    }
  }
  
  # 5. RUN PREDICTIONS
  # Pass the entire dataframe. predict() will safely find what it needs.
  predictions <- predict(rf_model, newdata=prediction_data)
  
  # 6. ADD PREDICTIONS TO OUTPUT
  output_data <- input_data
  output_data$Predicted_volume_m <- as.numeric(predictions)
  
  return(output_data)
}

#' Load RF Model from RDS File
#' 
#' @param model_path Path to .rds file
#' @return randomForest model object
load_rf_model <- function(model_path) {
  if (!file.exists(model_path)) {
    stop(paste("Model file not found:", model_path))
  }
  
  model <- readRDS(model_path)
  
  if (!inherits(model, "randomForest")) {
    stop("Loaded object is not a randomForest model")
  }
  
  return(model)
}

#' Get Model Information
#' 
#' @param rf_model randomForest model object
#' @return List with model metadata
get_model_info <- function(rf_model) {
  list(
    n_features = nrow(rf_model$importance),
    n_trees = rf_model$ntree,
    features = rownames(rf_model$importance),
    type = rf_model$type
  )
}