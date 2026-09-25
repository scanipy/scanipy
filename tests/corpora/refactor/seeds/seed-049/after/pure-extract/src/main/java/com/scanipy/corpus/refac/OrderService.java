package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input048) throws Exception {
        String left048 = "SELECT * FROM orders WHERE id = '";
        String right048 = "'";
        String value048 = _extracted_value(left048, input048, right048);
        Statement st = conn.createStatement();
        st.executeQuery(value048);
    }

    private static String _extracted_value(String left048, String input048, String right048) {
        return left048 + input048 + right048;
    }
}
