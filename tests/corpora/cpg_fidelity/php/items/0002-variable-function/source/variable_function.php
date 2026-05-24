<?php

// PHP variable function: $fn($arg) where $fn holds a function name at runtime.
// The call target is not statically fixed -> ground truth is a LOWER BOUND.
// Item carries the `dynamic` tag (DOC-CMP-CORP-CPG-php §3.3).

declare(strict_types=1);

namespace Corpus\VariableFunction;

function greet(string $name): string
{
    return "hello {$name}";
}

function shout(string $name): string
{
    return strtoupper($name);
}

function dispatch(string $which, string $name): string
{
    $fn = $which === "loud" ? "Corpus\\VariableFunction\\shout" : "Corpus\\VariableFunction\\greet";
    // Dynamic call site: target resolved at runtime from $fn.
    return $fn($name);
}

echo dispatch("loud", "world"), "\n";
