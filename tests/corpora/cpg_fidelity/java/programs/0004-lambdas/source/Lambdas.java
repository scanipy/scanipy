package corpus.cpg.p0004;

import java.util.function.Function;

/** Lambda call edges through LambdaMetafactory / INVOKEDYNAMIC. */
public final class Lambdas {

    static int apply(Function<Integer, Integer> f, int x) {
        return f.apply(x);
    }

    static int twice(int n) {
        return n * 2;
    }

    public static void main(String[] args) {
        Function<Integer, Integer> inc = x -> x + 1;
        int a = apply(inc, 10);
        int b = apply(n -> twice(n), 5);
        System.out.println(a + b);
    }
}
