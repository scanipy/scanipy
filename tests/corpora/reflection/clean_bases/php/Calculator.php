<?php
// Clean closed-world base - synthetic, no reflection / dynamic dispatch.
// Used as an injection target by pipeline/inject_reflection.py.
// Ground truth (pre-injection): closed-world.

class Calculator
{
    public function add($a, $b)
    {
        return $a + $b;
    }

    public function subtract($a, $b)
    {
        return $a - $b;
    }

    public function multiply($a, $b)
    {
        return $a * $b;
    }

    public function run($x, $y)
    {
        $s = $this->add($x, $y);
        $d = $this->subtract($x, $y);
        return $this->multiply($s, $d);
    }
}
