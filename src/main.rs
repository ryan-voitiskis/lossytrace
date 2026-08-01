use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(version, about = "Experimental audio compression-history evidence")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Emit verdict-free compression-trace measurements as JSON.
    Analyze {
        /// Audio file to decode and measure.
        audio: PathBuf,
        /// Maximum audio duration to inspect. Use 0 for the complete file.
        #[arg(long, default_value_t = 120.0)]
        max_seconds: f64,
        /// Pretty-print the JSON report.
        #[arg(long)]
        pretty: bool,
    },
}

fn run() -> Result<(), String> {
    match Cli::parse().command {
        Command::Analyze {
            audio,
            max_seconds,
            pretty,
        } => {
            if !max_seconds.is_finite() || max_seconds < 0.0 {
                return Err("--max-seconds must be finite and non-negative".to_owned());
            }
            let report =
                lossytrace::analyze_file(&audio, (max_seconds > 0.0).then_some(max_seconds))
                    .map_err(|error| error.to_string())?;
            let output = if pretty {
                serde_json::to_string_pretty(&report)
            } else {
                serde_json::to_string(&report)
            }
            .map_err(|error| format!("serialize evidence: {error}"))?;
            println!("{output}");
        }
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
