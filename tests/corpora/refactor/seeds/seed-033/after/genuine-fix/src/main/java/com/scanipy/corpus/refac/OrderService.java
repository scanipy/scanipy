package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input032) throws Exception {
        String left032 = "SELECT * FROM orders WHERE id = '";
        String right032 = "'";
        String value032 = "SELECT * FROM orders WHERE id = ?";
        java.sql.PreparedStatement st = conn.prepareStatement(value032);
        st.setString(1, input032);
        st.executeQuery();
    }
}
