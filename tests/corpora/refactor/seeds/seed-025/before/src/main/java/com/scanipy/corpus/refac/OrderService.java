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
        String value024 = left024 + input024 + right024;
        Statement st = conn.createStatement();
        st.executeQuery(value024);
    }
}
