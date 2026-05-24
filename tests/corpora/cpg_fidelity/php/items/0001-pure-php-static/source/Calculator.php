<?php

// Pure-PHP statically-resolvable control flow. No dynamic dispatch.
// Ground-truth call edges are an exact set (no dynamism -> upper bound = lower bound).

declare(strict_types=1);

namespace Corpus\PurePhp;

class Calculator
{
    public function add(int $a, int $b): int
    {
        return $a + $b;
    }

    public function doubleAdd(int $a, int $b): int
    {
        return $this->add($a, $b) + $this->add($a, $b);
    }
}

function run(int $x): int
{
    $calc = new Calculator();
    if ($x > 0) {
        return $calc->doubleAdd($x, $x);
    }
    return $calc->add($x, 1);
}

echo run(3), "\n";
