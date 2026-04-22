package domain

import (
	"errors"
	"strings"
	"time"
)

var AllowedCities = []string{"Sao Paulo", "Rio de Janeiro", "Brasilia", "Recife"}

func ValidateEmail(v string) error {
	if strings.TrimSpace(v) == "" || !strings.Contains(v, "@") {
		return errors.New("email invalido")
	}
	return nil
}

func ValidateDate(v string) error {
	_, err := time.Parse("2006-01-02", strings.TrimSpace(v))
	if err != nil {
		return errors.New("data invalida, use AAAA-MM-DD")
	}
	return nil
}

func ValidateDesiredBeforeCurrent(current, desired string) error {
	if err := ValidateDate(current); err != nil {
		return err
	}
	if err := ValidateDate(desired); err != nil {
		return err
	}
	c, _ := time.Parse("2006-01-02", current)
	d, _ := time.Parse("2006-01-02", desired)
	if !d.Before(c) {
		return errors.New("data desejada deve ser anterior a data atual")
	}
	return nil
}

func NormalizeCity(city string) (string, bool) {
	clean := strings.TrimSpace(strings.ToLower(city))
	for _, c := range AllowedCities {
		if strings.ToLower(c) == clean {
			return c, true
		}
	}
	return "", false
}
