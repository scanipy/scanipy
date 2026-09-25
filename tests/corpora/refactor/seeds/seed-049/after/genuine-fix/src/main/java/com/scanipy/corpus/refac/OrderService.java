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
        String value048 = "SELECT * FROM orders WHERE id = ?";
        java.sql.PreparedStatement st = conn.prepareStatement(value048);
        st.setString(1, input048);
        st.executeQuery();
    }
}
