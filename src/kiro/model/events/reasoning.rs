//! Reasoning content event
//!
//! Kiro CLI/IDE can stream model thinking as a separate `reasoningContentEvent`
//! instead of embedding `<thinking>...</thinking>` inside assistant text.

use serde::{Deserialize, Serialize};

use crate::kiro::parser::error::ParseResult;
use crate::kiro::parser::frame::Frame;

use super::base::EventPayload;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ReasoningContentEvent {
    #[serde(default)]
    pub text: String,

    #[serde(default)]
    pub signature: Option<String>,

    #[serde(default)]
    pub redacted_content: Option<String>,

    #[serde(flatten)]
    #[serde(skip_serializing)]
    #[allow(dead_code)]
    extra: serde_json::Value,
}

impl EventPayload for ReasoningContentEvent {
    fn from_frame(frame: &Frame) -> ParseResult<Self> {
        frame.payload_as_json()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_reasoning_content() {
        let json = r#"{"text":"thinking","signature":"sig-1","extraField":true}"#;
        let event: ReasoningContentEvent = serde_json::from_str(json).unwrap();

        assert_eq!(event.text, "thinking");
        assert_eq!(event.signature.as_deref(), Some("sig-1"));
    }
}
