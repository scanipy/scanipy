package rawprobe;

final class Flow {
    private String saved;

    static String helper(String left, String right) {
        String combined = left + ":" + right;
        return combined;
    }

    static String helper(int left, String right) {
        return right + left;
    }

    String instance(String value) {
        saved = value;
        return helper(value, saved);
    }

    static String variadic(String first, String... rest) {
        return first + rest[0];
    }

    String caller(String input, String[] values) {
        String named = helper(input, values[0]);
        String changed = helper(1, named);
        String result = this.instance(changed);
        return variadic(result, input, named);
    }

    String external(java.util.function.Function<String, String> target, String value) {
        return target.apply(value);
    }
}
