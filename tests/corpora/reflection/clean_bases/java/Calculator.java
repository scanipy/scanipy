// Clean closed-world base — synthetic, no reflection / dynamic dispatch.
// Used as an injection target by pipeline/inject_reflection.py.
// Ground truth (pre-injection): closed-world.
package com.scanipy.corpus.clean;

public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int subtract(int a, int b) {
        return a - b;
    }

    public int multiply(int a, int b) {
        return a * b;
    }

    public int run(int x, int y) {
        int s = add(x, y);
        int d = subtract(x, y);
        return multiply(s, d);
    }
}
