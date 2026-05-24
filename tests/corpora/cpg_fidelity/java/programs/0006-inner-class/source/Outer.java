package corpus.cpg.p0006;

/** Nested, static, and anonymous inner classes with enclosing-method edges. */
public final class Outer {

    private int base = 10;

    interface Greeter {
        String greet();
    }

    class Inner {
        int boosted() {
            return base + 5;
        }
    }

    static class StaticNested {
        int constant() {
            return 42;
        }
    }

    Greeter anon() {
        return new Greeter() {
            @Override
            public String greet() {
                return "hello " + base;
            }
        };
    }

    public static void main(String[] args) {
        Outer o = new Outer();
        Inner i = o.new Inner();
        StaticNested s = new StaticNested();
        System.out.println(i.boosted() + s.constant() + o.anon().greet());
    }
}
