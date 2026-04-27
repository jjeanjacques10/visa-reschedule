package contracts

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestParseTelegramPayload(t *testing.T) {
	data := []byte(`{"update_id":123,"message":{"chat":{"id":999999},"text":"/start"}}`)
	var upd TelegramUpdate
	if err := json.Unmarshal(data, &upd); err != nil {
		t.Fatal(err)
	}
	if upd.Message == nil || upd.Message.Chat.ID != 999999 {
		t.Fatal("payload invalido")
	}
}

func TestParseEventBridgePayload(t *testing.T) {
	data := []byte(`{"source":"visa-rescheduler.scheduler","detail-type":"dispatch-active-users"}`)
	var evt EventBridgeEvent
	if err := json.Unmarshal(data, &evt); err != nil {
		t.Fatal(err)
	}
	if evt.DetailType != "dispatch-active-users" {
		t.Fatal("detail-type invalido")
	}
}

func TestSQSSerialization(t *testing.T) {
	msg := SQSDispatchMessage{
		RequestID:              "uuid",
		ClientID:               "telegram-999",
		TelegramChatID:         "999",
		PortalUsername:         "user@email.com",
		PortalPassword:         "encrypted-password",
		CurrentAppointmentDate: "2026-09-20",
		DesiredAppointmentDate: "2026-07-15",
		City:                   "Sao Paulo",
	}
	data, err := json.Marshal(msg)
	if err != nil {
		t.Fatal(err)
	}
	var decoded map[string]any
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatal(err)
	}
	want := map[string]any{
		"request_id":               "uuid",
		"client_id":                "telegram-999",
		"telegram_chat_id":         "999",
		"portal_username":          "user@email.com",
		"portal_password":          "encrypted-password",
		"current_appointment_date": "2026-09-20",
		"desired_appointment_date": "2026-07-15",
		"city":                     "Sao Paulo",
	}
	if !reflect.DeepEqual(decoded, want) {
		t.Fatalf("unexpected json: %#v", decoded)
	}
}
