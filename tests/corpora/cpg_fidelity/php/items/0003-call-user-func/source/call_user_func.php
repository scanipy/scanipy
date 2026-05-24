<?php

// call_user_func / call_user_func_array indirection.
// Target passed as a callable value -> not statically fixed.
// Item carries the `dynamic` tag.

declare(strict_types=1);

namespace Corpus\CallUserFunc;

function formatUpper(string $s): string
{
    return strtoupper($s);
}

function apply(callable $cb, string $s): string
{
    // Dynamic call site: call_user_func dispatches to $cb at runtime.
    return call_user_func($cb, $s);
}

function applyArgs(callable $cb, array $args): string
{
    // Dynamic call site: call_user_func_array.
    return call_user_func_array($cb, $args);
}

echo apply("Corpus\\CallUserFunc\\formatUpper", "hi"), "\n";
echo applyArgs("Corpus\\CallUserFunc\\formatUpper", ["bye"]), "\n";
