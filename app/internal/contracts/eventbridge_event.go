package contracts

type EventBridgeEvent struct {
	Source     string         `json:"source"`
	DetailType string         `json:"detail-type"`
	Detail     map[string]any `json:"detail,omitempty"`
}
