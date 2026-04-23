package domain

import "testing"

func TestValidateDesiredBeforeCurrent(t *testing.T) {
	if err := ValidateDesiredBeforeCurrent("2026-09-20", "2026-07-15"); err != nil {
		t.Fatalf("expected valid: %v", err)
	}
	if err := ValidateDesiredBeforeCurrent("2026-09-20", "2026-10-01"); err == nil {
		t.Fatal("expected error when desired is after current")
	}
}

func TestNormalizeCity(t *testing.T) {
	if c, ok := NormalizeCity("sao paulo"); !ok || c != "Sao Paulo" {
		t.Fatal("expected Sao Paulo")
	}
}
