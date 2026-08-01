use std::fmt;

/// Errors returned while decoding or measuring audio evidence.
#[derive(Debug, Clone)]
pub enum AnalysisError {
    InvalidInput(String),
    DecodingError(String),
    NumericalError(String),
}

impl fmt::Display for AnalysisError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidInput(message) => write!(formatter, "invalid input: {message}"),
            Self::DecodingError(message) => write!(formatter, "decoding error: {message}"),
            Self::NumericalError(message) => write!(formatter, "numerical error: {message}"),
        }
    }
}

impl std::error::Error for AnalysisError {}
