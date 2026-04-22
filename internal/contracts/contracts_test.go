package contracts

import (
	"encoding/json"
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
	msg := SQSDispatchMessage{RequestID: "uuid", ClientID: "telegram-999", TelegramChatID: "999"}
	_, err := json.Marshal(msg)
	if err != nil {
		t.Fatal(err)
	}
}
