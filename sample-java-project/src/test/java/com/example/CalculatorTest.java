package com.example;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CalculatorTest {

    private Calculator calc;

    @BeforeEach
    void setUp() {
        calc = new Calculator();
    }

    @Test
    void testAdd() {
        assertEquals(5, calc.add(2, 3));
        assertEquals(0, calc.add(0, 0));
        assertEquals(-1, calc.add(-3, 2));
    }

    @Test
    void testSubtract() {
        assertEquals(1, calc.subtract(3, 2));
        assertEquals(-5, calc.subtract(0, 5));
    }

    @Test
    void testMultiply() {
        assertEquals(6, calc.multiply(2, 3));
        assertEquals(0, calc.multiply(5, 0));
        assertEquals(-6, calc.multiply(-2, 3));
    }

    @Test
    void testDivide() {
        assertEquals(2.0, calc.divide(6, 3), 0.001);
        assertEquals(2.5, calc.divide(5, 2), 0.001);
    }

    @Test
    void testDivideByZero() {
        assertThrows(IllegalArgumentException.class, () -> calc.divide(1, 0));
    }

    @Test
    void testMax() {
        assertEquals(5, calc.max(3, 5));
        assertEquals(5, calc.max(5, 3));
        assertEquals(4, calc.max(4, 4));
    }

    @Test
    void testIsEven() {
        assertTrue(calc.isEven(4));
        assertFalse(calc.isEven(3));
        assertTrue(calc.isEven(0));
    }

    @Test
    void testClamp() {
        assertEquals(5,  calc.clamp(5, 1, 10));
        assertEquals(1,  calc.clamp(-3, 1, 10));
        assertEquals(10, calc.clamp(15, 1, 10));
    }

    @Test
    void testFactorial() {
        assertEquals(1,   calc.factorial(0));
        assertEquals(1,   calc.factorial(1));
        assertEquals(120, calc.factorial(5));
    }

    @Test
    void testFactorialNegative() {
        assertThrows(IllegalArgumentException.class, () -> calc.factorial(-1));
    }
}