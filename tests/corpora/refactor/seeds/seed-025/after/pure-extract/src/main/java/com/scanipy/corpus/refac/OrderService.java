package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input024) throws Exception {
        String left024 = "SELECT * FROM orders WHERE id = '";
        String right024 = "'";
        String value024 = _extracted_value(left024, input024, right024);
        Statement st = conn.createStatement();
        st.executeQuery(value024);
    }

    private static String _extracted_value(String left024, String input024, String right024) {
        return left024 + input024 + right024;
    }
}
