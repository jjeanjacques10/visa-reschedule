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

func TestValidateDate(t *testing.T) {
	if err := ValidateDate("2026-09-20"); err != nil {
		t.Fatalf("expected valid date: %v", err)
	}
	if err := ValidateDate("2026-02-30"); err == nil {
		t.Fatal("expected error for invalid calendar date")
	}
}

func TestNormalizeCity(t *testing.T) {
	if c, ok := NormalizeCity("sao paulo"); !ok || c != "Sao Paulo" {
		t.Fatal("expected Sao Paulo")
	}
}
