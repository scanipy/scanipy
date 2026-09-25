package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input016) throws Exception {
        String left016 = "SELECT * FROM orders WHERE id = '";
        String right016 = "'";
        String value016 = _extracted_value(left016, input016, right016);
        Statement st = conn.createStatement();
        st.executeQuery(value016);
    }

    private static String _extracted_value(String left016, String input016, String right016) {
        return left016 + input016 + right016;
    }
}
