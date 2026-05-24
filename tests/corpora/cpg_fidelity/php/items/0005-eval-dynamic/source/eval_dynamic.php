<?php

// eval() of a runtime-constructed string. The called code does not exist as a
// static AST subtree -> any call inside the eval'd string is invisible to the
// front-end. Ground truth marks the eval site; no callee edge is asserted from
// it (undecidable). Item carries the `dynamic` tag.

declare(strict_types=1);

namespace Corpus\EvalDynamic;

function helper(int $n): int
{
    return $n * 2;
}

function compute(string $op, int $n): int
{
    $result = 0;
    // Dynamic code: eval target is a runtime string; callee is not statically known.
    eval("\$result = " . ($op === "double" ? "helper($n)" : "$n") . ";");
    return $result;
}

echo compute("double", 21), "\n";
