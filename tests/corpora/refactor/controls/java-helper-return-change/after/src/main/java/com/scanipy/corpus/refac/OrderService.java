package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input000) throws Exception {
        String left000 = "SELECT * FROM orders WHERE id = '";
        String right000 = "'";
        String value000 = _extracted_value(left000, input000, right000);
        Statement st = conn.createStatement();
        st.executeQuery(value000);
    }

    private static String _extracted_value(String left000, String input000, String right000) {
        return right000 + input000 + left000;
    }
}
