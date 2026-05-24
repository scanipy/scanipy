<?php

// Dynamic include: the included path is computed at runtime, so the set of
// symbols pulled into scope (and thus reachable call targets) is not statically
// fixed. Ground truth marks the include site; cross-file edges are a LOWER
// BOUND. Item carries the `dynamic` tag.

declare(strict_types=1);

namespace Corpus\IncludeDynamic;

function loadModule(string $name): void
{
    $base = __DIR__ . "/modules/";
    // Dynamic include: path resolved at runtime.
    include $base . $name . ".php";
}

function bootstrap(string $env): void
{
    loadModule($env === "prod" ? "prod_config" : "dev_config");
}

bootstrap("dev");
