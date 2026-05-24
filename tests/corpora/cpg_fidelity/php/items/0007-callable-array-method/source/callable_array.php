<?php

// Callable array form: [$object, 'method'] and ['Class', 'staticMethod'].
// The method name is a string -> the call target is not statically fixed when
// the name is data-derived. Item carries the `dynamic` tag.

declare(strict_types=1);

namespace Corpus\CallableArray;

class Handlers
{
    public function onStart(): string
    {
        return "start";
    }

    public function onStop(): string
    {
        return "stop";
    }
}

function trigger(Handlers $h, string $event): string
{
    $method = "on" . ucfirst($event);
    // Dynamic call site: [$object, $method] callable resolved at runtime.
    $callable = [$h, $method];
    return call_user_func($callable);
}

echo trigger(new Handlers(), "start"), "\n";
echo trigger(new Handlers(), "stop"), "\n";
