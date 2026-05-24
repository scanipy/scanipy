package corpus.cpg.p0005;

import java.util.function.Function;
import java.util.function.Supplier;

/** Method-reference (::) call-graph nodes. */
public final class MethodRefs {

    static String shout(String s) {
        return s.toUpperCase();
    }

    static String run(Function<String, String> f, String in) {
        return f.apply(in);
    }

    static String make(Supplier<String> s) {
        return s.get();
    }

    public static void main(String[] args) {
        String a = run(MethodRefs::shout, "hi");
        String b = make("x"::trim);
        System.out.println(a + b);
    }
}
