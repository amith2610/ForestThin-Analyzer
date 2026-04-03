# Random Forest Model Application Script
# Modified to work with Python integration via rpy2

library(randomForest)

#' Apply Random Forest Model to Input Data
#' 
#' @param input_data Data frame with required features
#' @param rf_model Loaded randomForest model object
#' @return Data frame with predictions added
apply_rf_model <- function(input_data, rf_model) {
  
  # Get required features from model
  required_features <- rownames(rf_model$importance)
  
  # Check for missing features
  missing_features <- setdiff(required_features, colnames(input_data))
  if (length(missing_features) > 0) {
    stop(paste("Missing required features:", paste(missing_features, collapse=", ")))
  }
  
  # Subset to required features only
  prediction_data <- input_data[, required_features, drop=FALSE]
  
  # Check for missing values
  if (any(is.na(prediction_data))) {
    warning("Input data contains missing values. Predictions may be incomplete.")
  }
  
  # Run predictions
  predictions <- predict(rf_model, newdata=prediction_data)
  
  # Add predictions to input data
  output_data <- input_data
  output_data$Predicted_volume_m <- predictions
  
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