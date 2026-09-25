package g1;

public final class SqlFlow {
    private static java.lang.String assemble(
            java.lang.String left,
            java.lang.String value,
            java.lang.String right) {
        java.lang.String joined = left + value;
        return joined + right;
    }

    public static void run(
            java.lang.String input,
            java.sql.Statement target) throws java.sql.SQLException {
        java.lang.String prefix = "SELECT * FROM records WHERE id = '";
        java.lang.String suffix = "'";
        java.lang.String query = assemble(prefix, input, suffix);
        target.executeQuery(query);
    }
}
