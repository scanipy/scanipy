<?php

// Magic method dispatch: __call / __callStatic.
// An undefined-method invocation is routed to __call at runtime; the real
// handler is selected inside __call. Static call-edge target is __call only;
// the downstream handler edge is a LOWER BOUND. Item carries the `dynamic` tag.

declare(strict_types=1);

namespace Corpus\MagicCall;

class Service
{
    private function handlePing(): string
    {
        return "pong";
    }

    private function handleEcho(string $s): string
    {
        return $s;
    }

    public function __call(string $name, array $args): string
    {
        // Dynamic dispatch: method name -> handler resolved at runtime.
        $handler = "handle" . ucfirst($name);
        return $this->$handler(...$args);
    }
}

$svc = new Service();
echo $svc->ping(), "\n";
echo $svc->echo("x"), "\n";
